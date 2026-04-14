from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest

from datum.config import settings


@pytest.fixture(autouse=True)
def setup_projects_root(tmp_path):
    settings.projects_root = tmp_path


@pytest.mark.asyncio
async def test_session_create_list_and_idempotency(client, monkeypatch, tmp_path):
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

    monkeypatch.setattr("datum.api.sessions.check_idempotency", fake_check)
    monkeypatch.setattr("datum.api.sessions.store_idempotency", fake_store)
    monkeypatch.setattr("datum.api.sessions._sync_session_note", fake_sync)
    monkeypatch.setattr("datum.api.sessions._get_project_row", fake_get_project_row)
    monkeypatch.setattr("datum.api.sessions.log_agent_audit", fake_log)

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
