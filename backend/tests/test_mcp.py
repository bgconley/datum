import json
from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest

from datum.mcp_server import create_mcp_server


class _FakeAsyncSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        del exc_type, exc, tb
        return False

    async def commit(self):
        return None

    async def rollback(self):
        return None


@pytest.mark.asyncio
async def test_mcp_server_registers_expected_tools_and_resources(tmp_path):
    project_dir = tmp_path / "alpha"
    project_dir.mkdir()
    (project_dir / "project.yaml").write_text("name: Alpha\nslug: alpha\n")
    docs_dir = project_dir / "docs"
    docs_dir.mkdir()
    (docs_dir / "overview.md").write_text("---\ntitle: Overview\ntype: plan\n---\n\nHello")

    mcp = create_mcp_server(tmp_path)

    tools = await mcp.list_tools()
    tool_names = [tool.name for tool in tools]
    assert tool_names == [
        "search_project_memory",
        "list_candidates",
        "resolve_citation",
        "get_project_context",
        "append_session_notes",
        "record_decision",
        "create_document",
        "update_document",
        "accept_candidate",
        "reject_candidate",
        "get_insights",
        "search_entity_relationships",
        "get_traceability",
    ]

    resources = await mcp.list_resources()
    assert [str(resource.uri) for resource in resources] == ["datum://projects"]

    templates = await mcp.list_resource_templates()
    assert {
        str(template.uriTemplate) for template in templates
    } == {
        "datum://projects/{slug}/context",
        "datum://projects/{slug}/tree",
        "datum://projects/{slug}/docs/{path}",
        "datum://projects/{slug}/decisions",
        "datum://projects/{slug}/requirements",
        "datum://projects/{slug}/open-questions",
        "datum://projects/{slug}/insights",
    }


@pytest.mark.asyncio
async def test_mcp_project_context_tool_returns_boundary_wrapped_payload(tmp_path):
    project_dir = tmp_path / "alpha"
    project_dir.mkdir()
    (project_dir / "project.yaml").write_text("name: Alpha\nslug: alpha\n")
    docs_dir = project_dir / "docs"
    docs_dir.mkdir()
    (docs_dir / "overview.md").write_text("---\ntitle: Overview\ntype: plan\n---\n\nHello")

    mcp = create_mcp_server(tmp_path)
    result = await mcp.call_tool("get_project_context", {"project": "alpha"})
    payload = json.loads(result[0].text)

    assert payload["content_kind"] == "retrieved_project_document"
    assert payload["data"]["project"]["name"] == "Alpha"


@pytest.mark.asyncio
async def test_mcp_search_records_preflight_when_session_id_present(tmp_path, monkeypatch):
    @dataclass(slots=True)
    class _Result:
        document_title: str = "Overview"
        document_path: str = "docs/overview.md"
        document_type: str = "plan"
        document_status: str = "active"
        project_slug: str = "alpha"
        heading_path: str = ""
        snippet: str = "Hello"
        version_number: int = 1
        content_hash: str = "sha256:abc"
        fused_score: float = 1.0
        matched_terms: list[str] = field(default_factory=list)
        document_uid: str = "doc_1"
        chunk_id: str = "chunk_1"
        line_start: int = 1
        line_end: int = 1
        match_signals: list[str] = field(default_factory=list)
        entities: list[object] = field(default_factory=list)

    class _Gateway:
        embedding = None
        reranker = None
        llm = None

        async def close(self):
            return None

    calls: list[tuple[str, str]] = []

    async def fake_record_preflight(session_id, action, db):
        del db
        calls.append((session_id, action))
        return True

    async def fake_search_execution(**kwargs):
        del kwargs
        return SimpleNamespace(results=[_Result()], entity_facets=[])

    monkeypatch.setattr("datum.mcp_server.async_session_factory", lambda: _FakeAsyncSession())
    monkeypatch.setattr("datum.mcp_server.record_preflight", fake_record_preflight)
    monkeypatch.setattr("datum.mcp_server.search_execution", fake_search_execution)
    monkeypatch.setattr("datum.mcp_server.build_model_gateway", lambda: _Gateway())

    mcp = create_mcp_server(tmp_path)
    result = await mcp.call_tool(
        "search_project_memory",
        {"query": "hello", "project": "alpha", "session_id": "ses_mcp_read"},
    )
    payload = json.loads(result[0].text)

    assert payload["result_count"] == 1
    assert calls == [("ses_mcp_read", "search_project_memory")]


@pytest.mark.asyncio
async def test_mcp_write_tool_returns_barrier_payload_when_blocked(tmp_path, monkeypatch):
    async def fake_evaluate_write_barrier(*, session_id, db, config):
        del session_id, db, config
        return SimpleNamespace(
            blocked=True,
            detail={"error": "preflight_required", "reason": "no_preflight"},
        )

    monkeypatch.setattr("datum.mcp_server.async_session_factory", lambda: _FakeAsyncSession())
    monkeypatch.setattr(
        "datum.mcp_server.evaluate_write_barrier",
        fake_evaluate_write_barrier,
    )

    mcp = create_mcp_server(tmp_path)
    result = await mcp.call_tool(
        "create_document",
        {
            "project": "alpha",
            "path": "docs/alpha.md",
            "title": "Alpha",
            "content": "# Alpha",
            "session_id": "ses_mcp_write",
        },
    )
    payload = json.loads(result[0].text)

    assert payload["error"] == "preflight_required"
    assert payload["reason"] == "no_preflight"
