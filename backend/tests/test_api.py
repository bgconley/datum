import json
from uuid import uuid4

import pytest

from datum.config import settings
from datum.services.search import SearchResult


@pytest.fixture(autouse=True)
def setup_projects_root(tmp_path):
    settings.projects_root = tmp_path


@pytest.mark.asyncio
async def test_create_and_list_projects(client):
    resp = await client.post("/api/v1/projects", json={
        "name": "Test Project", "slug": "test-project"
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["slug"] == "test-project"

    resp = await client.get("/api/v1/projects")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_create_and_get_document(client):
    await client.post("/api/v1/projects", json={"name": "P", "slug": "p"})
    resp = await client.post("/api/v1/projects/p/docs", json={
        "relative_path": "docs/notes.md",
        "title": "Notes",
        "doc_type": "brainstorm",
        "content": "# My Notes",
    })
    assert resp.status_code == 201
    assert resp.json()["version"] == 1

    resp = await client.get("/api/v1/projects/p/docs/docs/notes.md")
    assert resp.status_code == 200
    assert "# My Notes" in resp.json()["content"]


@pytest.mark.asyncio
async def test_save_document_with_conflict(client):
    await client.post("/api/v1/projects", json={"name": "P", "slug": "p"})
    await client.post("/api/v1/projects/p/docs", json={
        "relative_path": "docs/a.md",
        "title": "A",
        "doc_type": "plan",
        "content": "# A",
    })
    resp = await client.put("/api/v1/projects/p/docs/docs/a.md", json={
        "content": "# Updated",
        "base_hash": "sha256:wrong",
    })
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_save_document_success(client):
    await client.post("/api/v1/projects", json={"name": "P", "slug": "p"})
    await client.post("/api/v1/projects/p/docs", json={
        "relative_path": "docs/a.md",
        "title": "A",
        "doc_type": "plan",
        "content": "# V1",
    })
    # GET the full content (including frontmatter) for round-trip save
    resp = await client.get("/api/v1/projects/p/docs/docs/a.md")
    current_hash = resp.json()["metadata"]["content_hash"]
    full_content = resp.json()["content"]

    # Modify body, keep frontmatter
    modified = full_content.replace("# V1", "# V2 updated")
    resp = await client.put("/api/v1/projects/p/docs/docs/a.md", json={
        "content": modified,
        "base_hash": current_hash,
    })
    assert resp.status_code == 200
    assert resp.json()["version"] == 2


@pytest.mark.asyncio
async def test_create_document_rejects_non_docs_path(client):
    await client.post("/api/v1/projects", json={"name": "P", "slug": "p"})
    resp = await client.post("/api/v1/projects/p/docs", json={
        "relative_path": "project.yaml",
        "title": "Bad",
        "doc_type": "plan",
        "content": "# Bad",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_document_rejects_docs_prefix_traversal(client):
    await client.post("/api/v1/projects", json={"name": "P", "slug": "p"})
    resp = await client.post("/api/v1/projects/p/docs", json={
        "relative_path": "docs/../.piq/pwn.md",
        "title": "Bad",
        "doc_type": "plan",
        "content": "# Bad",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_document_db_sync_uses_normalized_canonical_path(client, monkeypatch):
    captured: dict[str, str] = {}

    async def fake_get_project_db_id(slug, session):
        del slug, session
        return uuid4()

    async def fake_sync_document_version_to_db(
        session,
        project_id,
        version_info,
        canonical_path,
        **kwargs,
    ):
        del session, project_id, version_info, kwargs
        captured["canonical_path"] = canonical_path

    async def fake_log_audit_event(
        session,
        actor_type,
        operation,
        project_id,
        target_path,
        **kwargs,
    ):
        del session, actor_type, operation, project_id, kwargs
        captured["target_path"] = target_path

    monkeypatch.setattr("datum.api.documents._get_project_db_id", fake_get_project_db_id)
    monkeypatch.setattr(
        "datum.api.documents.sync_document_version_to_db",
        fake_sync_document_version_to_db,
    )
    monkeypatch.setattr("datum.api.documents.log_audit_event", fake_log_audit_event)

    await client.post("/api/v1/projects", json={"name": "P", "slug": "p"})
    resp = await client.post("/api/v1/projects/p/docs", json={
        "relative_path": "docs/../docs/normalized.md",
        "title": "Normalized",
        "doc_type": "plan",
        "content": "# normalized",
    })

    assert resp.status_code == 201
    assert resp.json()["relative_path"] == "docs/normalized.md"
    assert captured["canonical_path"] == "docs/normalized.md"
    assert captured["target_path"] == "docs/normalized.md"


@pytest.mark.asyncio
async def test_save_document_db_sync_uses_normalized_canonical_path(client, monkeypatch):
    captured: dict[str, str] = {}

    async def fake_get_project_db_id(slug, session):
        del slug, session
        return uuid4()

    async def fake_sync_document_version_to_db(
        session,
        project_id,
        version_info,
        canonical_path,
        **kwargs,
    ):
        del session, project_id, version_info, kwargs
        captured["canonical_path"] = canonical_path

    async def fake_log_audit_event(
        session,
        actor_type,
        operation,
        project_id,
        target_path,
        **kwargs,
    ):
        del session, actor_type, operation, project_id, kwargs
        captured["target_path"] = target_path

    monkeypatch.setattr("datum.api.documents._get_project_db_id", fake_get_project_db_id)
    monkeypatch.setattr(
        "datum.api.documents.sync_document_version_to_db",
        fake_sync_document_version_to_db,
    )
    monkeypatch.setattr("datum.api.documents.log_audit_event", fake_log_audit_event)

    await client.post("/api/v1/projects", json={"name": "P", "slug": "p"})
    create_resp = await client.post("/api/v1/projects/p/docs", json={
        "relative_path": "docs/normalized-save.md",
        "title": "Normalized Save",
        "doc_type": "plan",
        "content": "# V1",
    })
    assert create_resp.status_code == 201

    current = await client.get("/api/v1/projects/p/docs/docs/normalized-save.md")
    current_hash = current.json()["metadata"]["content_hash"]
    updated = current.json()["content"].replace("# V1", "# V2")

    resp = await client.put("/api/v1/projects/p/docs/docs/../docs/normalized-save.md", json={
        "content": updated,
        "base_hash": current_hash,
    })
    assert resp.status_code == 200
    assert resp.json()["relative_path"] == "docs/normalized-save.md"
    assert captured["canonical_path"] == "docs/normalized-save.md"
    assert captured["target_path"] == "docs/normalized-save.md"


@pytest.mark.asyncio
async def test_create_project_rejects_bad_slug(client):
    resp = await client.post("/api/v1/projects", json={
        "name": "Bad", "slug": "../escape"
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_put_round_trip_no_duplicate_frontmatter(client):
    """Finding 2: GET content fed back to PUT must not duplicate frontmatter."""
    await client.post("/api/v1/projects", json={"name": "P", "slug": "p"})
    await client.post("/api/v1/projects/p/docs", json={
        "relative_path": "docs/rt.md",
        "title": "Round Trip",
        "doc_type": "plan",
        "content": "# Original body",
    })

    # GET the full content (includes frontmatter)
    resp = await client.get("/api/v1/projects/p/docs/docs/rt.md")
    assert resp.status_code == 200
    full_content = resp.json()["content"]
    current_hash = resp.json()["metadata"]["content_hash"]
    assert "title: Round Trip" in full_content

    # Modify the body portion, keeping frontmatter intact
    modified = full_content.replace("# Original body", "# Modified body")

    # PUT the full content back
    resp = await client.put("/api/v1/projects/p/docs/docs/rt.md", json={
        "content": modified,
        "base_hash": current_hash,
    })
    assert resp.status_code == 200
    assert resp.json()["version"] == 2

    # GET again and verify no duplicated frontmatter
    resp = await client.get("/api/v1/projects/p/docs/docs/rt.md")
    final_content = resp.json()["content"]
    assert final_content.count("title: Round Trip") == 1
    assert "# Modified body" in final_content


@pytest.mark.asyncio
async def test_put_missing_document_returns_404(client):
    """Finding 3: PUT on missing document should return 404, not 500."""
    await client.post("/api/v1/projects", json={"name": "P", "slug": "p"})
    resp = await client.put("/api/v1/projects/p/docs/docs/missing.md", json={
        "content": "# Content",
        "base_hash": "sha256:fake",
    })
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_stale_pending_commit_returns_503(client, tmp_path):
    """Stale pending_commit on save should return 503, not 500."""
    from datum.config import settings
    await client.post("/api/v1/projects", json={"name": "P2", "slug": "p2"})
    await client.post("/api/v1/projects/p2/docs", json={
        "relative_path": "docs/stale.md",
        "title": "Stale",
        "doc_type": "plan",
        "content": "# Stale test",
    })

    # Inject stale pending_commit with existing version file
    from datum.services.filesystem import doc_manifest_dir, read_manifest, write_manifest
    project_path = settings.projects_root / "p2"
    manifest_dir = doc_manifest_dir(project_path, "docs/stale.md")
    manifest_path = manifest_dir / "manifest.yaml"
    manifest = read_manifest(manifest_path)
    manifest["pending_commit"] = {
        "version": 2,
        "branch": "main",
        "file": "main/v002.md",
        "content_hash": "sha256:fake",
        "canonical_path": "docs/stale.md",
        "started": "2026-04-12T00:00:00+00:00",
    }
    write_manifest(manifest_path, manifest)
    # Create the orphaned version file so StalePendingCommitError triggers
    (manifest_dir / "main" / "v002.md").write_bytes(b"orphaned")

    # Get current hash for a valid save attempt
    resp = await client.get("/api/v1/projects/p2/docs/docs/stale.md")
    current_hash = resp.json()["metadata"]["content_hash"]
    full_content = resp.json()["content"]
    modified = full_content.replace("# Stale test", "# Modified")

    resp = await client.put("/api/v1/projects/p2/docs/docs/stale.md", json={
        "content": modified,
        "base_hash": current_hash,
    })
    assert resp.status_code == 503
    assert "stale pending commit" in resp.json()["detail"]["message"]


@pytest.mark.asyncio
async def test_manifest_conflict_on_get_returns_503(client):
    """ManifestLayoutConflictError on GET doc should return 503, not 500."""
    from datum.config import settings
    from datum.services.filesystem import write_manifest

    await client.post("/api/v1/projects", json={"name": "Conflict", "slug": "conflict"})
    await client.post("/api/v1/projects/conflict/docs", json={
        "relative_path": "docs/dup.md",
        "title": "Dup",
        "doc_type": "plan",
        "content": "# Dup",
    })

    # Create legacy dir alongside the new dir to trigger conflict
    project_path = settings.projects_root / "conflict"
    legacy_dir = project_path / ".piq" / "docs" / "dup"
    legacy_dir.mkdir(parents=True, exist_ok=True)
    write_manifest(legacy_dir / "manifest.yaml", {
        "document_uid": "doc_legacy",
        "canonical_path": "docs/dup.md",
        "branches": {},
    })

    resp = await client.get("/api/v1/projects/conflict/docs/docs/dup.md")
    assert resp.status_code == 503
    assert "layout conflict" in resp.json()["detail"]["message"].lower()


@pytest.mark.asyncio
async def test_manifest_conflict_on_list_returns_503(client):
    """ManifestLayoutConflictError on list docs should return 503, not 500."""
    from datum.config import settings
    from datum.services.filesystem import write_manifest

    await client.post("/api/v1/projects", json={"name": "Conflict2", "slug": "conflict2"})
    await client.post("/api/v1/projects/conflict2/docs", json={
        "relative_path": "docs/dup.md",
        "title": "Dup",
        "doc_type": "plan",
        "content": "# Dup",
    })

    project_path = settings.projects_root / "conflict2"
    legacy_dir = project_path / ".piq" / "docs" / "dup"
    legacy_dir.mkdir(parents=True, exist_ok=True)
    write_manifest(legacy_dir / "manifest.yaml", {
        "document_uid": "doc_legacy",
        "canonical_path": "docs/dup.md",
        "branches": {},
    })

    resp = await client.get("/api/v1/projects/conflict2/docs")
    assert resp.status_code == 503
    assert "layout conflict" in resp.json()["detail"]["message"].lower()


@pytest.mark.asyncio
async def test_search_returns_results(client, monkeypatch):
    class StubGateway:
        embedding = None
        reranker = None

        async def close(self):
            return None

    async def fake_search(**kwargs):
        return []

    monkeypatch.setattr("datum.api.search.build_model_gateway", lambda: StubGateway())
    monkeypatch.setattr("datum.api.search.search", fake_search)

    resp = await client.post("/api/v1/search", json={"query": "test"})
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert data["result_count"] == 0


@pytest.mark.asyncio
async def test_search_rejects_invalid_as_of_scope(client):
    resp = await client.post(
        "/api/v1/search",
        json={"query": "test", "version_scope": "as_of:not-a-timestamp"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_search_serializes_nonempty_results(client, monkeypatch):
    class StubGateway:
        embedding = None
        reranker = None

        async def close(self):
            return None

    async def fake_search(**kwargs):
        return [
            SearchResult(
                document_title="Search Doc",
                document_path="docs/search.md",
                project_slug="p",
                heading_path="Intro",
                snippet="Use DATABASE_URL on port 8001.",
                version_number=2,
                content_hash="sha256:abc",
                fused_score=0.42,
                matched_terms=["DATABASE_URL"],
                document_uid="doc_123",
                chunk_id="chunk_123",
                line_start=3,
                line_end=5,
            )
        ]

    monkeypatch.setattr("datum.api.search.build_model_gateway", lambda: StubGateway())
    monkeypatch.setattr("datum.api.search.search", fake_search)

    resp = await client.post("/api/v1/search", json={"query": "DATABASE_URL", "project": "p"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["result_count"] == 1
    assert data["results"][0]["document_title"] == "Search Doc"
    assert data["results"][0]["matched_terms"] == ["DATABASE_URL"]


@pytest.mark.asyncio
async def test_search_stream_emits_phases(client, monkeypatch):
    class StubGateway:
        embedding = None
        reranker = object()

        async def close(self):
            return None

    async def fake_stream_search(**kwargs):
        yield type(
            "Execution",
            (),
            {
                "phase": "lexical",
                "query": "DATABASE_URL",
                "results": [],
                "latency_ms": 4,
                "semantic_enabled": False,
                "rerank_applied": False,
            },
        )()
        yield type(
            "Execution",
            (),
            {
                "phase": "reranked",
                "query": "DATABASE_URL",
                "results": [
                    SearchResult(
                        document_title="Search Doc",
                        document_path="docs/search.md",
                        project_slug="p",
                        heading_path="Intro",
                        snippet="Use DATABASE_URL on port 8001.",
                        version_number=2,
                        content_hash="sha256:abc",
                        fused_score=0.42,
                        matched_terms=["DATABASE_URL"],
                        document_uid="doc_123",
                        chunk_id="chunk_123",
                        line_start=3,
                        line_end=5,
                        match_signals=["keyword", "exact-term"],
                    )
                ],
                "latency_ms": 12,
                "semantic_enabled": False,
                "rerank_applied": True,
            },
        )()

    monkeypatch.setattr("datum.api.search.build_model_gateway", lambda: StubGateway())
    monkeypatch.setattr("datum.api.search.stream_search", fake_stream_search)

    async with client.stream(
        "POST",
        "/api/v1/search/stream",
        json={"query": "DATABASE_URL"},
    ) as resp:
        assert resp.status_code == 200
        lines = [json.loads(line) async for line in resp.aiter_lines() if line]

    assert [line["phase"] for line in lines] == ["lexical", "reranked"]
    assert lines[1]["results"][0]["match_signals"] == ["keyword", "exact-term"]
    assert lines[1]["rerank_applied"] is True


class _EvalScalarResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items


class _EvalSession:
    def __init__(self):
        self.sets = []
        self.runs = []

    def add(self, obj):
        if obj.__class__.__name__ == "EvaluationSet":
            if getattr(obj, "id", None) is None:
                obj.id = "eval-set-id"
            self.sets.append(obj)
        else:
            self.runs.append(obj)

    async def commit(self):
        return None

    async def refresh(self, obj):
        return None

    async def execute(self, statement, params=None):
        rendered = str(statement)
        if "FROM evaluation_sets" in rendered:
            return _EvalScalarResult(list(self.sets))
        if "FROM evaluation_runs" in rendered:
            return _EvalScalarResult(list(self.runs))
        return _EvalScalarResult([])

    async def get(self, model, key):
        name = model.__name__
        if name == "EvaluationRun":
            return next((item for item in self.runs if str(item.id) == str(key)), None)
        if name == "EvaluationSet":
            return next((item for item in self.sets if str(item.id) == str(key)), None)
        return None


@pytest.mark.asyncio
async def test_eval_set_crud(client):
    from datum.db import get_session
    from datum.main import app

    session = _EvalSession()

    async def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        resp = await client.post(
            "/api/v1/eval/sets",
            json={
                "name": "test-set",
                "queries": [{"query": "test", "expected_results": [{"doc_path": "docs/a.md"}]}],
            },
        )
        assert resp.status_code == 201
        assert resp.json()["query_count"] == 1

        resp = await client.get("/api/v1/eval/sets")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_eval_run_and_stats(client, monkeypatch):
    from datum.db import get_session
    from datum.main import app

    session = _EvalSession()

    async def override_get_session():
        yield session

    class StubGateway:
        embedding = None
        reranker = None

        async def close(self):
            return None

    async def fake_run_evaluation(**kwargs):
        from datum.models.evaluation import EvaluationRun

        run = EvaluationRun(
            id=uuid.uuid4(),
            evaluation_set_id=uuid.uuid4(),
            name=kwargs["run_name"],
            version_scope="current",
            results={"ndcg_at_5": 1.0},
        )
        session.runs.append(run)
        return run, {"ndcg_at_5": 1.0}

    async def fake_stats(_session):
        return [{"model_name": "Qwen3-Embedding-4B", "model_run_id": "run-1", "embedding_count": 5}]

    import uuid

    app.dependency_overrides[get_session] = override_get_session
    monkeypatch.setattr("datum.api.evaluation.build_model_gateway", lambda: StubGateway())
    monkeypatch.setattr("datum.api.evaluation.run_evaluation", fake_run_evaluation)
    monkeypatch.setattr("datum.api.evaluation.get_embedding_stats", fake_stats)
    try:
        resp = await client.post(
            "/api/v1/eval/runs",
            json={"eval_set_id": str(uuid.uuid4()), "name": "baseline", "version_scope": "current"},
        )
        assert resp.status_code == 201
        assert resp.json()["results"]["ndcg_at_5"] == 1.0

        resp = await client.get("/api/v1/eval/runs")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

        resp = await client.get("/api/v1/eval/stats")
        assert resp.status_code == 200
        assert resp.json()["models"][0]["embedding_count"] == 5
    finally:
        app.dependency_overrides.clear()
