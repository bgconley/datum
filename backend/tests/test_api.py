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
