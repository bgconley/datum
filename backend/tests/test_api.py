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
    from datum.services.filesystem import read_manifest, write_manifest, doc_manifest_dir
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
