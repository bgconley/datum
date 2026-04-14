from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from datum.config import settings
from datum.db import get_session
from datum.services.write_barrier import require_preflight


@pytest.fixture(autouse=True)
def setup_projects_root(tmp_path):
    settings.projects_root = tmp_path


@pytest.mark.asyncio
async def test_session_create_list_and_idempotency(client, monkeypatch, tmp_path):
    from datum.main import app

    project_dir = tmp_path / "api-test"
    project_dir.mkdir()
    (project_dir / "project.yaml").write_text("name: API Test\nslug: api-test\n")

    cached: dict[str, dict] = {}

    async def fake_check(_session, key, scope=None):
        payload = cached.get(f"{scope}:{key}")
        if payload is None:
            return None
        return {"status_code": 201, "body": payload}

    async def fake_store(_session, key, scope, status_code, response_body):
        del status_code
        cached[f"{scope}:{key}"] = response_body

    async def fake_sync(**kwargs):
        del kwargs
        return None

    async def fake_get_project_row(slug, session):
        del slug, session
        return None

    async def fake_log(*args, **kwargs):
        del args, kwargs
        return None

    async def fake_record_delta(*args, **kwargs):
        del args, kwargs
        return None

    async def allow_preflight():
        return None

    monkeypatch.setattr("datum.api.sessions.check_idempotency", fake_check)
    monkeypatch.setattr("datum.api.sessions.store_idempotency", fake_store)
    monkeypatch.setattr("datum.api.sessions._sync_session_note", fake_sync)
    monkeypatch.setattr("datum.api.sessions._get_project_row", fake_get_project_row)
    monkeypatch.setattr("datum.api.sessions.log_agent_audit", fake_log)
    monkeypatch.setattr("datum.api.sessions.record_delta", fake_record_delta)
    app.dependency_overrides[require_preflight] = allow_preflight
    try:
        resp = await client.post(
            "/api/v1/projects/api-test/sessions",
            headers={"X-Idempotency-Key": "idem-1"},
            json={
                "session_id": "sess-1",
                "agent_name": "codex",
                "summary": "Test session",
                "content": "## Work\nCreated the note.",
            },
        )
        assert resp.status_code == 201
        payload = resp.json()
        assert payload["session_id"] == "sess-1"
        assert payload["path"].startswith("docs/sessions/")

        second = await client.post(
            "/api/v1/projects/api-test/sessions",
            headers={"X-Idempotency-Key": "idem-1"},
            json={
                "session_id": "sess-1",
                "agent_name": "codex",
                "summary": "Test session",
                "content": "## Work\nCreated the note.",
            },
        )
        assert second.status_code == 201
        assert second.text == resp.text
        assert second.json()["path"] == payload["path"]

        listed = await client.get("/api/v1/projects/api-test/sessions")
        assert listed.status_code == 200
        assert listed.json()["sessions"][0]["session_id"] == "sess-1"
    finally:
        app.dependency_overrides.pop(require_preflight, None)


@pytest.mark.asyncio
async def test_context_and_citation_endpoints(client, tmp_path):
    project_dir = tmp_path / "api-test"
    project_dir.mkdir()
    (project_dir / "project.yaml").write_text("name: API Test\nslug: api-test\n")
    docs_dir = project_dir / "docs"
    docs_dir.mkdir()
    (docs_dir / "overview.md").write_text("---\ntitle: Overview\ntype: plan\n---\n\nHello world.")

    manifest_dir = project_dir / ".piq" / "docs" / "overview.md" / "main"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "v001.md").write_text("line1\nline2\nline3\nline4")
    (
        project_dir / ".piq" / "docs" / "overview.md" / "manifest.yaml"
    ).write_text(
        "document_uid: doc_1\n"
        "canonical_path: docs/overview.md\n"
        "branches:\n"
        "  main:\n"
        "    head: v001\n"
        "    versions:\n"
        "      - version: 1\n"
        "        file: main/v001.md\n"
        "        content_hash: sha256:abc\n"
        "        created: '2026-04-13T00:00:00+00:00'\n"
    )

    context_resp = await client.get("/api/v1/projects/api-test/context?detail=brief&max_tokens=200")
    assert context_resp.status_code == 200
    context_payload = context_resp.json()
    assert context_payload["content_kind"] == "retrieved_project_document"
    assert "project" in context_payload["data"]

    citation_resp = await client.post(
        "/api/v1/citations/resolve",
        json={
            "source_ref": {
                "project_slug": "api-test",
                "document_uid": "doc_1",
                "version_number": 1,
                "content_hash": "sha256:abc",
                "chunk_id": "chunk_1",
                "canonical_path": "docs/overview.md",
                "heading_path": [],
                "line_start": 2,
                "line_end": 3,
            }
        },
    )
    assert citation_resp.status_code == 200
    assert citation_resp.json()["content"] == "line2\nline3"


@pytest.mark.asyncio
async def test_search_answer_mode(client, monkeypatch):
    @dataclass(slots=True)
    class _Result:
        document_title: str = "Auth"
        document_path: str = "docs/auth.md"
        document_type: str = "decision"
        document_status: str = "accepted"
        project_slug: str = "api-test"
        heading_path: str = "Overview"
        snippet: str = "JWT auth is used."
        version_number: int = 3
        content_hash: str = "sha256:abc"
        fused_score: float = 1.0
        matched_terms: list[str] = field(default_factory=list)
        document_uid: str = "doc_1"
        chunk_id: str = "chunk_1"
        line_start: int = 10
        line_end: int = 20
        match_signals: list[str] = field(default_factory=list)
        entities: list[object] = field(default_factory=list)

    execution = SimpleNamespace(results=[_Result()], entity_facets=[])

    async def fake_search_execution(**kwargs):
        del kwargs
        return execution

    async def fake_generate_answer(gateway, query, results):
        del gateway, query, results
        return SimpleNamespace(
            answer="Use JWT auth [1].",
            citations=[
                SimpleNamespace(
                    index=1,
                    human_readable='api-test/docs/auth.md v3, section "Overview"',
                    source_ref=SimpleNamespace(
                        project_slug="api-test",
                        document_uid="doc_1",
                        version_number=3,
                        content_hash="sha256:abc",
                        chunk_id="chunk_1",
                        canonical_path="docs/auth.md",
                        heading_path=["Overview"],
                        line_start=10,
                        line_end=20,
                    ),
                )
            ],
            error="",
            model="gpt-oss-20b",
        )

    class _Gateway:
        embedding = None
        reranker = None
        llm = object()

        async def close(self):
            return None

    monkeypatch.setattr("datum.api.search.search_execution", fake_search_execution)
    monkeypatch.setattr("datum.api.search.generate_answer", fake_generate_answer)
    monkeypatch.setattr("datum.api.search.build_model_gateway", lambda: _Gateway())

    resp = await client.post(
        "/api/v1/search",
        json={"query": "How does auth work?", "answer_mode": True},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["answer"]["answer"] == "Use JWT auth [1]."
    assert payload["answer"]["citations"][0]["source_ref"]["document_uid"] == "doc_1"


@pytest.mark.asyncio
async def test_lifecycle_api_endpoints(client):
    from datum.main import app

    class _DummySession:
        async def commit(self):
            return None

    async def fake_get_db():
        yield _DummySession()

    state = {
        "session_id": "ses_test_api_lifecycle",
        "status": "active",
        "enforcement_mode": "blocking",
        "is_dirty": False,
        "dirty_reasons": {},
        "last_preflight_at": None,
        "last_preflight_action": None,
        "last_flush_at": None,
        "started_at": "2026-04-14T00:00:00+00:00",
        "ended_at": None,
        "deltas": [],
    }

    async def fake_start_session(*, session_id, project_slug, client_type, db):
        del project_slug, client_type, db
        return SimpleNamespace(
            id="row-1",
            session_id=session_id,
            project_id=None,
            client_type="generic",
            status=state["status"],
            enforcement_mode=state["enforcement_mode"],
            is_dirty=state["is_dirty"],
            started_at=state["started_at"],
        )

    async def fake_record_preflight(session_id, action, db):
        del db
        state["session_id"] = session_id
        state["last_preflight_at"] = "2026-04-14T00:01:00+00:00"
        state["last_preflight_action"] = action
        return True

    async def fake_record_delta(session_id, delta_type, detail, db, summary_text=None):
        del db, summary_text
        state["session_id"] = session_id
        state["is_dirty"] = True
        state["dirty_reasons"] = {delta_type: 1}
        delta = SimpleNamespace(
            id="delta-1",
            delta_type=delta_type,
            detail=detail,
            flushed=False,
            created_at="2026-04-14T00:02:00+00:00",
        )
        state["deltas"] = [delta]
        return delta

    async def fake_get_session_by_session_id(session_id, db):
        del db
        return SimpleNamespace(
            session_id=session_id,
            status=state["status"],
            enforcement_mode=state["enforcement_mode"],
            is_dirty=state["is_dirty"],
            dirty_reasons=state["dirty_reasons"],
            last_preflight_at=state["last_preflight_at"],
            last_preflight_action=state["last_preflight_action"],
            last_flush_at=state["last_flush_at"],
            started_at=state["started_at"],
            ended_at=state["ended_at"],
        )

    async def fake_get_unflushed_deltas(session_id, db):
        del session_id, db
        return state["deltas"]

    async def fake_flush_deltas(session_id, db, write_session_note=True):
        del session_id, db, write_session_note
        state["is_dirty"] = False
        state["dirty_reasons"] = {}
        state["last_flush_at"] = "2026-04-14T00:03:00+00:00"
        for delta in state["deltas"]:
            delta.flushed = True
        return SimpleNamespace(
            flushed_count=1,
            summary=SimpleNamespace(
                counts={"command_run": 1},
                recent_paths=[],
                recent_commands=["pytest -q"],
            ),
            session_note_path="docs/sessions/ses_test_api_lifecycle.md",
        )

    async def fake_evaluate_stop_barrier(session_id, db, *, enforcement_mode):
        del session_id, db, enforcement_mode
        return SimpleNamespace(blocked=False, detail={})

    async def fake_finalize_session(session_id, db):
        del db
        state["status"] = "finalized"
        state["ended_at"] = "2026-04-14T00:04:00+00:00"
        return SimpleNamespace(
            session_id=session_id,
            status="finalized",
            ended_at=state["ended_at"],
        )

    app.dependency_overrides[get_session] = fake_get_db
    try:
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr("datum.api.lifecycle.start_session", fake_start_session)
        monkeypatch.setattr("datum.api.lifecycle.record_preflight", fake_record_preflight)
        monkeypatch.setattr("datum.api.lifecycle.record_delta", fake_record_delta)
        monkeypatch.setattr(
            "datum.api.lifecycle.get_session_by_session_id",
            fake_get_session_by_session_id,
        )
        monkeypatch.setattr(
            "datum.api.lifecycle.get_unflushed_deltas",
            fake_get_unflushed_deltas,
        )
        monkeypatch.setattr("datum.api.lifecycle.flush_deltas", fake_flush_deltas)
        monkeypatch.setattr(
            "datum.api.lifecycle.evaluate_stop_barrier",
            fake_evaluate_stop_barrier,
        )
        monkeypatch.setattr("datum.api.lifecycle.finalize_session", fake_finalize_session)

        session_id = state["session_id"]

        started = await client.post(
            "/api/v1/agent/sessions/start",
            json={"session_id": session_id, "client_type": "generic"},
        )
        assert started.status_code == 201
        assert started.json()["session_id"] == session_id

        preflight = await client.post(
            f"/api/v1/agent/sessions/{session_id}/preflight",
            json={"action": "get_project_context"},
        )
        assert preflight.status_code == 200
        assert preflight.json()["recorded"] is True

        delta = await client.post(
            f"/api/v1/agent/sessions/{session_id}/delta",
            json={"delta_type": "command_run", "detail": {"command": "pytest -q"}},
        )
        assert delta.status_code == 201
        assert delta.json()["delta_type"] == "command_run"

        status = await client.get(f"/api/v1/agent/sessions/{session_id}/status")
        assert status.status_code == 200
        assert status.json()["is_dirty"] is True
        assert status.json()["unflushed_delta_count"] == 1

        flush = await client.post(f"/api/v1/agent/sessions/{session_id}/flush")
        assert flush.status_code == 200
        assert flush.json()["flushed_count"] == 1

        finalized = await client.post(f"/api/v1/agent/sessions/{session_id}/finalize")
        assert finalized.status_code == 200
        assert finalized.json()["status"] == "finalized"
    finally:
        app.dependency_overrides.pop(get_session, None)
        monkeypatch.undo()


@pytest.mark.asyncio
async def test_blocking_lifecycle_enforcement_on_session_notes(client, monkeypatch, tmp_path):
    old_mode = settings.lifecycle_enforcement_mode
    settings.lifecycle_enforcement_mode = "blocking"
    try:
        from datum.main import app

        class _DummySession:
            async def commit(self):
                return None

        async def fake_get_db():
            yield _DummySession()

        project_dir = tmp_path / "blocked-project"
        project_dir.mkdir()
        (project_dir / "project.yaml").write_text("name: Blocked\nslug: blocked-project\n")

        cached: dict[str, dict] = {}

        async def fake_check(_session, key, scope=None):
            payload = cached.get(f"{scope}:{key}")
            if payload is None:
                return None
            return {"status_code": 201, "body": payload}

        async def fake_store(_session, key, scope, status_code, response_body):
            del status_code
            cached[f"{scope}:{key}"] = response_body

        async def fake_sync(**kwargs):
            del kwargs
            return None

        async def fake_get_project_row(slug, session):
            del slug, session
            return None

        async def fake_log(*args, **kwargs):
            del args, kwargs
            return None

        async def fake_record_delta(*args, **kwargs):
            del args, kwargs
            return None

        async def blocked_preflight():
            raise HTTPException(
                status_code=428,
                detail={"error": "preflight_required", "reason": "no_preflight"},
            )

        async def allowed_preflight():
            return None

        async def fake_get_session_by_session_id(session_id, db):
            del session_id, db
            return SimpleNamespace(
                session_id="ses_blocking_enforced",
                status="active",
                enforcement_mode="blocking",
                is_dirty=True,
                dirty_reasons={"doc_create": 1},
                last_preflight_at="2026-04-14T00:01:00+00:00",
                last_preflight_action="get_project_context",
                last_flush_at=None,
                started_at="2026-04-14T00:00:00+00:00",
                ended_at=None,
            )

        async def fake_start_session(*, session_id, project_slug, client_type, db):
            del project_slug, client_type, db
            return SimpleNamespace(
                id="row-block",
                session_id=session_id,
                project_id=None,
                client_type="generic",
                status="active",
                enforcement_mode="blocking",
                is_dirty=False,
                started_at="2026-04-14T00:00:00+00:00",
            )

        async def fake_evaluate_stop_barrier(session_id, db, *, enforcement_mode):
            del session_id, db, enforcement_mode
            return SimpleNamespace(
                blocked=True,
                detail={"error": "dirty_session", "unflushed_delta_count": 1},
            )

        async def fake_record_preflight(session_id, action, db):
            del session_id, action, db
            return True

        monkeypatch.setattr("datum.api.sessions.check_idempotency", fake_check)
        monkeypatch.setattr("datum.api.sessions.store_idempotency", fake_store)
        monkeypatch.setattr("datum.api.sessions._sync_session_note", fake_sync)
        monkeypatch.setattr("datum.api.sessions._get_project_row", fake_get_project_row)
        monkeypatch.setattr("datum.api.sessions.log_agent_audit", fake_log)
        monkeypatch.setattr("datum.api.sessions.record_delta", fake_record_delta)
        monkeypatch.setattr(
            "datum.api.lifecycle.get_session_by_session_id",
            fake_get_session_by_session_id,
        )
        monkeypatch.setattr("datum.api.lifecycle.start_session", fake_start_session)
        monkeypatch.setattr(
            "datum.api.lifecycle.evaluate_stop_barrier",
            fake_evaluate_stop_barrier,
        )
        monkeypatch.setattr("datum.api.lifecycle.record_preflight", fake_record_preflight)

        app.dependency_overrides[get_session] = fake_get_db
        app.dependency_overrides[require_preflight] = blocked_preflight

        lifecycle_session = "ses_blocking_enforced"
        await client.post(
            "/api/v1/agent/sessions/start",
            json={
                "session_id": lifecycle_session,
                "project_slug": "blocked-project",
                "client_type": "generic",
            },
        )

        blocked = await client.post(
            "/api/v1/projects/blocked-project/sessions",
            headers={"X-Session-ID": lifecycle_session},
            json={
                "session_id": lifecycle_session,
                "agent_name": "codex",
                "summary": "Blocked write",
                "content": "This should be rejected first.",
            },
        )
        assert blocked.status_code == 428
        assert blocked.json()["detail"]["error"] == "preflight_required"

        app.dependency_overrides[require_preflight] = allowed_preflight

        preflight = await client.post(
            f"/api/v1/agent/sessions/{lifecycle_session}/preflight",
            json={"action": "get_project_context"},
        )
        assert preflight.status_code == 200

        created = await client.post(
            "/api/v1/projects/blocked-project/sessions",
            headers={"X-Session-ID": lifecycle_session},
            json={
                "session_id": lifecycle_session,
                "agent_name": "codex",
                "summary": "Allowed write",
                "content": "This should succeed after preflight.",
            },
        )
        assert created.status_code == 201

        dirty_finalize = await client.post(
            f"/api/v1/agent/sessions/{lifecycle_session}/finalize"
        )
        assert dirty_finalize.status_code == 409
        assert dirty_finalize.json()["detail"]["error"] == "dirty_session"
    finally:
        from datum.main import app

        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(require_preflight, None)
        settings.lifecycle_enforcement_mode = old_mode
