import json

import pytest

from datum.mcp_server import create_mcp_server


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
