import pytest

from datum.config import settings


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
    # Get current hash
    resp = await client.get("/api/v1/projects/p/docs/docs/a.md")
    current_hash = resp.json()["metadata"]["content_hash"]

    resp = await client.put("/api/v1/projects/p/docs/docs/a.md", json={
        "content": "# V2 updated",
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
async def test_create_project_rejects_bad_slug(client):
    resp = await client.post("/api/v1/projects", json={
        "name": "Bad", "slug": "../escape"
    })
    assert resp.status_code == 422
