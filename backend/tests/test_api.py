import json
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from datum.config import settings
from datum.services.search import (
    SearchEntityFacet,
    SearchExecution,
    SearchResult,
    SearchResultEntity,
)


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
async def test_project_workspace_snapshot_endpoint(client):
    await client.post("/api/v1/projects", json={"name": "Workspace", "slug": "workspace"})
    created = await client.post("/api/v1/projects/workspace/docs", json={
        "relative_path": "docs/overview.md",
        "title": "Overview",
        "doc_type": "plan",
        "content": "# Overview",
    })
    assert created.status_code == 201

    resp = await client.get("/api/v1/projects/workspace/workspace")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["project"]["slug"] == "workspace"
    assert payload["documents"][0]["relative_path"] == "docs/overview.md"
    generated_paths = [item["relative_path"] for item in payload["generated_files"]]
    assert ".piq/docs/overview.md/manifest.yaml" in generated_paths


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
async def test_version_history_endpoints(client):
    await client.post("/api/v1/projects", json={"name": "P", "slug": "p"})
    await client.post("/api/v1/projects/p/docs", json={
        "relative_path": "docs/a.md",
        "title": "A",
        "doc_type": "plan",
        "content": "# V1",
    })

    current = await client.get("/api/v1/projects/p/docs/docs/a.md")
    assert current.status_code == 200
    current_hash = current.json()["metadata"]["content_hash"]
    updated = current.json()["content"].replace("# V1", "# V2 updated")

    saved = await client.put("/api/v1/projects/p/docs/docs/a.md", json={
        "content": updated,
        "base_hash": current_hash,
    })
    assert saved.status_code == 200

    versions = await client.get("/api/v1/projects/p/docs/docs/a.md/versions")
    assert versions.status_code == 200
    version_payload = versions.json()
    assert [entry["version_number"] for entry in version_payload] == [1, 2]
    assert version_payload[0]["change_source"] == "web"

    version_one = await client.get("/api/v1/projects/p/docs/docs/a.md/versions/1")
    assert version_one.status_code == 200
    assert "# V1" in version_one.json()["content"]

    diff = await client.get("/api/v1/projects/p/docs/docs/a.md/versions/diff/1/2")
    assert diff.status_code == 200
    diff_payload = diff.json()
    assert diff_payload["version_a"] == 1
    assert diff_payload["version_b"] == 2
    assert diff_payload["additions"] > 0 or diff_payload["deletions"] > 0
    assert "V2 updated" in diff_payload["diff_text"]


@pytest.mark.asyncio
async def test_restore_version_endpoint(client):
    await client.post("/api/v1/projects", json={"name": "P", "slug": "p"})
    await client.post("/api/v1/projects/p/docs", json={
        "relative_path": "docs/a.md",
        "title": "A",
        "doc_type": "plan",
        "content": "# V1",
    })

    current = await client.get("/api/v1/projects/p/docs/docs/a.md")
    hash_v1 = current.json()["metadata"]["content_hash"]
    full_content = current.json()["content"]

    saved = await client.put("/api/v1/projects/p/docs/docs/a.md", json={
        "content": full_content.replace("# V1", "# V2"),
        "base_hash": hash_v1,
    })
    assert saved.status_code == 200

    restored = await client.post(
        "/api/v1/projects/p/docs/docs/a.md/versions/1/restore",
        json={"label": "Back to v1"},
    )
    assert restored.status_code == 200
    assert restored.json()["version"] == 3

    latest = await client.get("/api/v1/projects/p/docs/docs/a.md")
    assert latest.status_code == 200
    assert "# V1" in latest.json()["content"]

    versions = await client.get("/api/v1/projects/p/docs/docs/a.md/versions")
    assert versions.status_code == 200
    assert versions.json()[-1]["restored_from"] == 1
    assert versions.json()[-1]["label"] == "Back to v1"


@pytest.mark.asyncio
async def test_move_document_endpoint(client):
    await client.post("/api/v1/projects", json={"name": "P", "slug": "p"})
    created = await client.post("/api/v1/projects/p/docs", json={
        "relative_path": "docs/notes.md",
        "title": "Notes",
        "doc_type": "plan",
        "content": "# Notes",
    })
    assert created.status_code == 201

    moved = await client.post(
        "/api/v1/projects/p/docs/docs/notes.md/move",
        json={"new_relative_path": "docs/archive/renamed-notes.md"},
    )
    assert moved.status_code == 200
    assert moved.json()["relative_path"] == "docs/archive/renamed-notes.md"

    old_doc = await client.get("/api/v1/projects/p/docs/docs/notes.md")
    assert old_doc.status_code == 404

    new_doc = await client.get("/api/v1/projects/p/docs/docs/archive/renamed-notes.md")
    assert new_doc.status_code == 200
    assert "# Notes" in new_doc.json()["content"]

    versions = await client.get("/api/v1/projects/p/docs/docs/archive/renamed-notes.md/versions")
    assert versions.status_code == 200
    assert len(versions.json()) == 1


@pytest.mark.asyncio
async def test_create_folder_and_list_generated_files(client):
    await client.post("/api/v1/projects", json={"name": "P", "slug": "p"})

    folder = await client.post(
        "/api/v1/projects/p/docs/folders",
        json={"relative_path": "docs/adr"},
    )
    assert folder.status_code == 201
    assert folder.json()["relative_path"] == "docs/adr"

    created = await client.post("/api/v1/projects/p/docs", json={
        "relative_path": "docs/adr/decision.md",
        "title": "Decision",
        "doc_type": "decision",
        "content": "# Decision",
    })
    assert created.status_code == 201

    generated = await client.get("/api/v1/projects/p/docs/generated")
    assert generated.status_code == 200
    generated_paths = [item["relative_path"] for item in generated.json()]
    assert ".piq/docs/adr/decision.md/manifest.yaml" in generated_paths


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
async def test_templates_endpoints(client):
    templates = await client.get("/api/v1/templates")
    assert templates.status_code == 200
    payload = templates.json()
    assert len(payload) >= 4
    assert any(item["name"] == "adr" for item in payload)

    template = await client.get("/api/v1/templates/adr")
    assert template.status_code == 200
    assert template.json()["doc_type"] == "decision"

    rendered = await client.get("/api/v1/templates/adr/render?title=ADR-9000")
    assert rendered.status_code == 200
    assert "ADR-9000" in rendered.json()["content"]


@pytest.mark.asyncio
async def test_delete_document_endpoint_soft_deletes_and_archives(client):
    await client.post("/api/v1/projects", json={"name": "P", "slug": "p"})
    created = await client.post("/api/v1/projects/p/docs", json={
        "relative_path": "docs/delete-me.md",
        "title": "Delete Me",
        "doc_type": "plan",
        "content": "# delete me",
    })
    assert created.status_code == 201

    deleted = await client.delete("/api/v1/projects/p/docs/docs/delete-me.md")
    assert deleted.status_code == 200
    archived_path = deleted.json()["archived_path"]
    assert archived_path.startswith(".piq/deleted/docs/delete-me.md.")

    get_deleted = await client.get("/api/v1/projects/p/docs/docs/delete-me.md")
    assert get_deleted.status_code == 404

    archived_file = settings.projects_root / "p" / archived_path
    assert archived_file.exists()
    assert "# delete me" in archived_file.read_text()


class _ScalarListResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return list(self._items)


class _ScalarResult:
    def __init__(self, item=None, items=None):
        self._item = item
        self._items = items or []

    def scalar_one_or_none(self):
        return self._item

    def scalars(self):
        return _ScalarListResult(self._items)


class _RowResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return list(self._rows)


class _SavedSearchSession:
    def __init__(self):
        from datum.models.operational import SavedSearch

        self._model = SavedSearch
        self.records = []

    def add(self, record):
        if record.id is None:
            record.id = uuid4()
        if record.created_at is None:
            record.created_at = datetime.now(UTC)
        self.records.append(record)

    async def flush(self):
        return None

    async def commit(self):
        return None

    async def delete(self, record):
        self.records = [item for item in self.records if item.id != record.id]

    async def execute(self, statement):
        rendered = str(statement)
        if "FROM saved_searches" in rendered:
            return _ScalarResult(items=self.records)
        return _ScalarResult()

    async def get(self, model, key):
        if model is not self._model:
            return None
        key_str = str(key)
        return next((item for item in self.records if str(item.id) == key_str), None)


class _CollectionSession:
    def __init__(self, project_id, document):
        from datum.models.operational import Collection, CollectionMember

        self._collection_model = Collection
        self._member_model = CollectionMember
        self.project_id = project_id
        self.document = document
        self.collections = []
        self.members = []

    def add(self, record):
        if hasattr(record, "id") and getattr(record, "id", None) is None:
            record.id = uuid4()
        if getattr(record, "created_at", None) is None and hasattr(record, "created_at"):
            record.created_at = datetime.now(UTC)
        if getattr(record, "added_at", None) is None and hasattr(record, "added_at"):
            record.added_at = datetime.now(UTC)
        if record.__class__ is self._collection_model:
            self.collections.append(record)
        elif record.__class__ is self._member_model:
            self.members.append(record)

    async def flush(self):
        return None

    async def commit(self):
        return None

    async def delete(self, record):
        if record.__class__ is self._collection_model:
            self.collections = [item for item in self.collections if item.id != record.id]
        elif record.__class__ is self._member_model:
            self.members = [
                item
                for item in self.members
                if not (
                    item.collection_id == record.collection_id
                    and item.document_id == record.document_id
                )
            ]

    async def execute(self, statement):
        rendered = str(statement)
        if "collection_members" in rendered and "documents" in rendered:
            rows = [
                (
                    self.document.uid,
                    self.document.title,
                    self.document.canonical_path,
                    member.added_at,
                )
                for member in self.members
            ]
            return _RowResult(rows)
        if "FROM documents" in rendered:
            return _ScalarResult(item=self.document)
        if "FROM collections" in rendered and "count(collection_members.document_id)" in rendered:
            rows = [
                (
                    collection.id,
                    collection.name,
                    collection.description,
                    collection.created_at,
                    sum(1 for member in self.members if member.collection_id == collection.id),
                )
                for collection in self.collections
            ]
            return _RowResult(rows)
        return _ScalarResult()

    async def get(self, model, key):
        if model is self._collection_model:
            key_str = str(key)
            return next((item for item in self.collections if str(item.id) == key_str), None)
        if model is self._member_model:
            collection_id = key["collection_id"]
            document_id = key["document_id"]
            return next(
                (
                    item
                    for item in self.members
                    if item.collection_id == collection_id and item.document_id == document_id
                ),
                None,
            )
        return None


class _AnnotationSession:
    def __init__(self, version_id):
        from datum.models.core import DocumentVersion
        from datum.models.operational import Annotation

        self._version_model = DocumentVersion
        self._annotation_model = Annotation
        self.version = DocumentVersion(
            id=version_id,
            document_id=uuid4(),
            version_number=1,
            branch="main",
            content_hash="sha256:test",
            filesystem_path=".piq/test",
        )
        self.annotations = []

    def add(self, record):
        if getattr(record, "id", None) is None:
            record.id = uuid4()
        if getattr(record, "created_at", None) is None:
            record.created_at = datetime.now(UTC)
        self.annotations.append(record)

    async def flush(self):
        return None

    async def commit(self):
        return None

    async def delete(self, record):
        self.annotations = [item for item in self.annotations if item.id != record.id]

    async def execute(self, statement):
        rendered = str(statement)
        if "FROM annotations" in rendered:
            return _ScalarResult(items=self.annotations)
        return _ScalarResult()

    async def get(self, model, key):
        if model is self._version_model:
            return self.version if UUID(str(key)) == self.version.id else None
        if model is self._annotation_model:
            key_uuid = UUID(str(key))
            return next((item for item in self.annotations if item.id == key_uuid), None)
        return None


class _UploadSession:
    async def execute(self, statement):
        del statement
        return _ScalarResult(item=None)

    async def commit(self):
        return None

    async def rollback(self):
        return None


@pytest.mark.asyncio
async def test_saved_searches_crud_endpoint(client):
    from datum.db import get_session
    from datum.main import app
    from datum.models.core import Project

    project = Project(
        id=uuid4(),
        uid="proj_saved",
        slug="saved",
        name="Saved",
        filesystem_path="/tmp/saved",
    )
    session = _SavedSearchSession()

    async def override_get_session():
        yield session

    async def fake_get_project(slug, async_session):
        del async_session
        assert slug == "saved"
        return project

    app.dependency_overrides[get_session] = override_get_session
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("datum.api.saved_searches._get_project", fake_get_project)
    try:
        created = await client.post(
            "/api/v1/projects/saved/saved-searches",
            json={
                "name": "Updated docs",
                "query_text": "Updated via API",
                "filters": {"scope": "current"},
            },
        )
        assert created.status_code == 201

        listed = await client.get("/api/v1/projects/saved/saved-searches")
        assert listed.status_code == 200
        assert listed.json()[0]["name"] == "Updated docs"

        deleted = await client.delete(
            f"/api/v1/projects/saved/saved-searches/{created.json()['id']}",
        )
        assert deleted.status_code == 200
    finally:
        monkeypatch.undo()
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_collection_membership_endpoints_use_document_uid(client):
    from datum.db import get_session
    from datum.main import app
    from datum.models.core import Document, Project

    project = Project(
        id=uuid4(),
        uid="proj_coll",
        slug="coll",
        name="Collections",
        filesystem_path="/tmp/coll",
    )
    document = Document(
        id=uuid4(),
        uid="doc_coll",
        project_id=project.id,
        slug="doc",
        canonical_path="docs/doc.md",
        title="Doc",
        doc_type="plan",
    )
    session = _CollectionSession(project.id, document)

    async def override_get_session():
        yield session

    async def fake_get_project(slug, async_session):
        del async_session
        assert slug == "coll"
        return project

    async def fake_get_collection(slug, collection_id, async_session):
        del slug, async_session
        collection = next(
            (item for item in session.collections if str(item.id) == collection_id),
            None,
        )
        assert collection is not None
        return collection

    app.dependency_overrides[get_session] = override_get_session
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("datum.api.collections._get_project", fake_get_project)
    monkeypatch.setattr("datum.api.collections._get_collection", fake_get_collection)
    try:
        created = await client.post(
            "/api/v1/projects/coll/collections",
            json={"name": "Auth collection", "description": "docs"},
        )
        assert created.status_code == 201
        collection_id = created.json()["id"]

        added = await client.post(
            f"/api/v1/projects/coll/collections/{collection_id}/members",
            json={"document_uid": document.uid},
        )
        assert added.status_code == 201

        listed = await client.get(f"/api/v1/projects/coll/collections/{collection_id}/members")
        assert listed.status_code == 200
        assert listed.json()[0]["document_uid"] == document.uid

        removed = await client.delete(
            f"/api/v1/projects/coll/collections/{collection_id}/members/{document.uid}",
        )
        assert removed.status_code == 200
        assert removed.json()["status"] == "removed"
    finally:
        monkeypatch.undo()
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_annotations_crud_endpoint(client):
    from datum.db import get_session
    from datum.main import app

    version_id = uuid4()
    session = _AnnotationSession(version_id)

    async def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        created = await client.post(
            "/api/v1/annotations",
            json={
                "version_id": str(version_id),
                "annotation_type": "comment",
                "content": "Check this evidence",
                "start_char": 0,
                "end_char": 12,
            },
        )
        assert created.status_code == 201

        listed = await client.get(f"/api/v1/annotations?version_id={version_id}")
        assert listed.status_code == 200
        assert listed.json()[0]["annotation_type"] == "comment"

        deleted = await client.delete(f"/api/v1/annotations/{created.json()['id']}")
        assert deleted.status_code == 200
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_upload_endpoint_writes_blob_and_attachment_metadata(client, tmp_blobs):
    from datum.db import get_session
    from datum.main import app

    del tmp_blobs
    settings.blobs_root = settings.projects_root.parent / "blobs"
    settings.blobs_root.mkdir(parents=True, exist_ok=True)
    await client.post("/api/v1/projects", json={"name": "Uploads", "slug": "uploads"})

    async def override_get_session():
        yield _UploadSession()

    app.dependency_overrides[get_session] = override_get_session
    try:
        response = await client.post(
            "/api/v1/projects/uploads/upload",
            files={"file": ("notes.txt", b"phase-8 upload", "text/plain")},
        )
        assert response.status_code == 201
        payload = response.json()
        assert payload["attachment_path"].startswith("attachments/notes-")
        assert payload["content_hash"].startswith("sha256:")
        metadata_file = settings.projects_root / "uploads" / payload["attachment_path"]
        assert metadata_file.exists()
        assert "blob_ref" in metadata_file.read_text()
    finally:
        app.dependency_overrides.clear()


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
async def test_intelligence_inbox_and_summary_endpoints(client, monkeypatch):
    async def fake_list_candidates(session, slug):
        del session
        assert slug == "intel"
        return [
            SimpleNamespace(
                id="dec-1",
                candidate_type="decision",
                title="Use ParadeDB",
                context="Need hybrid search.",
                severity="high",
                decision="Use ParadeDB for BM25 plus pgvector.",
                consequences="Single database.",
                description=None,
                priority=None,
                resolution=None,
                curation_status="candidate",
                extraction_method="structured_adr",
                confidence=1.0,
                source_doc_path="docs/decisions/adr-0001.md",
                source_version=1,
                created_at="2026-04-13T00:00:00+00:00",
            ),
            SimpleNamespace(
                id="req-1",
                candidate_type="requirement",
                title="The UI must show inbox counts.",
                context="Surface pending candidate counts in navigation.",
                severity="high",
                decision=None,
                consequences=None,
                description="Surface pending candidate counts in navigation.",
                priority="must",
                resolution=None,
                curation_status="candidate",
                extraction_method="regex_req_id",
                confidence=0.95,
                source_doc_path="docs/decisions/adr-0001.md",
                source_version=1,
                created_at="2026-04-13T00:00:00+00:00",
            ),
        ]

    async def fake_summary(session, slug):
        del session
        assert slug == "intel"
        return SimpleNamespace(
            pending_candidate_count=2,
            key_entities=[
                SimpleNamespace(
                    entity_type="technology",
                    canonical_name="paradedb",
                    count=2,
                )
            ],
            open_questions=[
                SimpleNamespace(
                    id="oq-1",
                    question="What is the rollback plan?",
                    context="Need a production fallback before rollout.",
                    age_days=41,
                    is_stale=True,
                    source_doc_path="docs/ops/rollout.md",
                    source_version=3,
                    canonical_record_path=".piq/records/open-questions/oq_1.yaml",
                    created_at="2026-04-13T00:00:00+00:00",
                )
            ],
        )

    monkeypatch.setattr("datum.api.inbox.list_candidates", fake_list_candidates)
    monkeypatch.setattr(
        "datum.api.inbox.get_project_intelligence_summary",
        fake_summary,
    )

    inbox = await client.get("/api/v1/projects/intel/inbox")
    assert inbox.status_code == 200
    items = inbox.json()
    assert [item["candidate_type"] for item in items] == ["decision", "requirement"]
    assert items[0]["severity"] == "high"
    assert items[0]["source_doc_path"] == "docs/decisions/adr-0001.md"

    summary = await client.get("/api/v1/projects/intel/intelligence/summary")
    assert summary.status_code == 200
    summary_payload = summary.json()
    assert summary_payload["pending_candidate_count"] == 2
    assert summary_payload["key_entities"][0]["canonical_name"] == "paradedb"
    assert summary_payload["key_entities"][0]["count"] == 2
    assert summary_payload["open_questions"][0]["question"] == "What is the rollback plan?"
    assert summary_payload["open_questions"][0]["is_stale"] is True


@pytest.mark.asyncio
async def test_inbox_accept_and_reject_actions_persist_curated_records(client, monkeypatch):
    async def fake_accept_candidate(session, *, slug, candidate_type, candidate_id, body):
        del session, body
        assert slug == "inbox"
        assert candidate_type == "decision"
        assert candidate_id == "dec-1"
        return SimpleNamespace(
            id="dec-1",
            curation_status="edited",
            canonical_record_path=".piq/records/decisions/dec_test.yaml",
        )

    async def fake_reject_candidate(session, *, slug, candidate_type, candidate_id):
        del session
        assert slug == "inbox"
        assert candidate_type == "open_question"
        assert candidate_id == "oq-1"
        return SimpleNamespace(
            id="oq-1",
            curation_status="rejected",
            canonical_record_path=None,
        )

    monkeypatch.setattr("datum.api.inbox.accept_candidate", fake_accept_candidate)
    monkeypatch.setattr("datum.api.inbox.reject_candidate", fake_reject_candidate)

    accepted = await client.post(
        "/api/v1/projects/inbox/inbox/decision/dec-1/accept",
        json={
            "title": "Use a preflight write barrier",
            "decision": "Require get_project_context before mutating state.",
            "consequences": "Agent writes become explicitly gated.",
        },
    )
    assert accepted.status_code == 200
    accepted_payload = accepted.json()
    assert accepted_payload["curation_status"] == "edited"
    assert accepted_payload["canonical_record_path"] == ".piq/records/decisions/dec_test.yaml"

    rejected = await client.post(
        "/api/v1/projects/inbox/inbox/open_question/oq-1/reject"
    )
    assert rejected.status_code == 200
    assert rejected.json()["curation_status"] == "rejected"


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
        del kwargs
        return SearchExecution(
            phase="hybrid",
            query="test",
            results=[],
            fused_results=[],
            latency_ms=4,
            semantic_enabled=False,
            rerank_applied=False,
            entity_facets=[],
        )

    monkeypatch.setattr("datum.api.search.build_model_gateway", lambda: StubGateway())
    monkeypatch.setattr("datum.api.search.search_execution", fake_search)

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
        del kwargs
        return SearchExecution(
            phase="hybrid",
            query="DATABASE_URL",
            results=[
                SearchResult(
                    document_title="Search Doc",
                    document_path="docs/search.md",
                    document_type="note",
                    document_status="draft",
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
                    entities=[
                        SearchResultEntity(
                            canonical_name="database_url",
                            entity_type="api endpoint",
                        )
                    ],
                )
            ],
            fused_results=[],
            latency_ms=6,
            semantic_enabled=False,
            rerank_applied=False,
            entity_facets=[
                SearchEntityFacet(
                    canonical_name="database_url",
                    entity_type="api endpoint",
                    count=1,
                )
            ],
        )

    monkeypatch.setattr("datum.api.search.build_model_gateway", lambda: StubGateway())
    monkeypatch.setattr("datum.api.search.search_execution", fake_search)

    resp = await client.post("/api/v1/search", json={"query": "DATABASE_URL", "project": "p"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["result_count"] == 1
    assert data["results"][0]["document_title"] == "Search Doc"
    assert data["results"][0]["matched_terms"] == ["DATABASE_URL"]
    assert data["results"][0]["entities"][0]["canonical_name"] == "database_url"
    assert data["entity_facets"][0]["canonical_name"] == "database_url"


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
                "entity_facets": [],
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
                        document_type="note",
                        document_status="draft",
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
                        entities=[
                            SearchResultEntity(
                                canonical_name="database_url",
                                entity_type="api endpoint",
                            )
                        ],
                    )
                ],
                "entity_facets": [
                    SearchEntityFacet(
                        canonical_name="database_url",
                        entity_type="api endpoint",
                        count=1,
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
    assert lines[1]["entity_facets"][0]["canonical_name"] == "database_url"
    assert lines[1]["rerank_applied"] is True


@pytest.mark.asyncio
async def test_traceability_and_insights_endpoints(client, monkeypatch):
    async def fake_list_links(session, slug, limit=200):
        del session, limit
        assert slug == "intel"
        return [
            SimpleNamespace(
                id="link-1",
                source_document_path="docs/requirements/auth.md",
                target_document_path="docs/decisions/adr-auth.md",
                link_type="implements",
                anchor_text="ADR auth",
                auto_detected=True,
                confidence=0.98,
                created_at="2026-04-13T00:00:00+00:00",
            )
        ]

    async def fake_list_relationships(
        session,
        slug,
        entity_name=None,
        relationship_type=None,
        limit=200,
    ):
        del session, limit
        assert slug == "intel"
        assert entity_name == "postgresql"
        assert relationship_type == "uses"
        return [
            SimpleNamespace(
                id="rel-1",
                source_entity="auth service",
                target_entity="postgresql",
                relationship_type="uses",
                extraction_method="llm",
                evidence_text="Auth service stores sessions in PostgreSQL.",
                evidence_document_path="docs/architecture.md",
                evidence_document_title="Architecture",
                evidence_heading_path="Storage",
                evidence_version_number=4,
                evidence_chunk_id="chunk-rel-1",
                evidence_start_char=128,
                evidence_end_char=168,
                confidence=0.82,
                created_at="2026-04-13T00:00:00+00:00",
            )
        ]

    async def fake_list_insights(session, slug, status=None, limit=100):
        del session, limit
        assert slug == "intel"
        assert status == "open"
        return [
            SimpleNamespace(
                id="insight-1",
                insight_type="stale_document",
                severity="warning",
                status="open",
                title="Architecture doc looks stale",
                explanation="No updates in 75 days.",
                confidence=0.77,
                evidence={"document_path": "docs/architecture.md"},
                created_at="2026-04-13T00:00:00+00:00",
                resolved_at=None,
            )
        ]

    async def fake_analyze_insights(session, slug, max_age_days=60):
        del session
        assert slug == "intel"
        assert max_age_days == 45
        return SimpleNamespace(
            contradictions_found=1,
            staleness_found=2,
            insights_created=2,
            insights_skipped=1,
        )

    async def fake_update_insight_status(session, slug, insight_id, status):
        del session
        assert slug == "intel"
        assert insight_id == "insight-1"
        assert status == "resolved"
        return SimpleNamespace(
            id="insight-1",
            insight_type="stale_document",
            severity="warning",
            status="resolved",
            title="Architecture doc looks stale",
            explanation="No updates in 75 days.",
            confidence=0.77,
            evidence={"document_path": "docs/architecture.md"},
            created_at="2026-04-13T00:00:00+00:00",
            resolved_at="2026-04-13T01:00:00+00:00",
        )

    async def fake_traceability(session, slug):
        del session
        assert slug == "intel"
        return [
            SimpleNamespace(
                requirement=SimpleNamespace(
                    uid="req_auth",
                    title="System must support JWT auth",
                    status="active",
                    description="JWT login support",
                    priority="must",
                    decision=None,
                    name=None,
                    entity_type=None,
                ),
                decisions=[
                    SimpleNamespace(
                        uid="dec_auth",
                        title="Use signed JWT tokens",
                        status="accepted",
                        description="docs/decisions/adr-auth.md",
                        priority=None,
                        decision="Adopt JWT",
                        name=None,
                        entity_type=None,
                    )
                ],
                schema_entities=[
                    SimpleNamespace(
                        uid=None,
                        title=None,
                        status=None,
                        description=None,
                        priority=None,
                        decision=None,
                        name="sessions.user_id",
                        entity_type="column",
                    )
                ],
            )
        ]

    monkeypatch.setattr("datum.api.traceability.list_project_links", fake_list_links)
    monkeypatch.setattr(
        "datum.api.traceability.list_project_entity_relationships",
        fake_list_relationships,
    )
    monkeypatch.setattr("datum.api.traceability.list_project_insights", fake_list_insights)
    monkeypatch.setattr(
        "datum.api.traceability.analyze_project_insights",
        fake_analyze_insights,
    )
    monkeypatch.setattr(
        "datum.api.traceability.update_project_insight_status",
        fake_update_insight_status,
    )
    monkeypatch.setattr("datum.api.traceability.get_traceability_chains", fake_traceability)

    links = await client.get("/api/v1/projects/intel/links")
    assert links.status_code == 200
    assert links.json()["links"][0]["target_document_path"] == "docs/decisions/adr-auth.md"

    relationships = await client.get(
        "/api/v1/projects/intel/relationships",
        params={"entity_name": "postgresql", "relationship_type": "uses"},
    )
    assert relationships.status_code == 200
    relationship = relationships.json()["relationships"][0]
    assert relationship["source_entity"] == "auth service"
    assert relationship["relationship_type"] == "uses"
    assert relationship["evidence_document_path"] == "docs/architecture.md"
    assert relationship["evidence_version_number"] == 4
    assert relationship["evidence_chunk_id"] == "chunk-rel-1"

    insights = await client.get("/api/v1/projects/intel/insights", params={"status": "open"})
    assert insights.status_code == 200
    assert insights.json()["insights"][0]["title"] == "Architecture doc looks stale"

    analysis = await client.post(
        "/api/v1/projects/intel/insights/analyze",
        params={"max_age_days": 45},
    )
    assert analysis.status_code == 200
    assert analysis.json()["insights_created"] == 2

    resolved = await client.post(
        "/api/v1/projects/intel/insights/insight-1/status",
        json={"status": "resolved"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"

    traceability = await client.get("/api/v1/projects/intel/traceability")
    assert traceability.status_code == 200
    chain = traceability.json()[0]
    assert chain["requirement"]["uid"] == "req_auth"
    assert chain["decisions"][0]["uid"] == "dec_auth"
    assert chain["schema_entities"][0]["name"] == "sessions.user_id"


@pytest.mark.asyncio
async def test_entities_endpoints(client, monkeypatch):
    async def fake_list_entities(session, slug, entity_type=None, limit=100):
        del session, limit
        assert slug == "intel"
        assert entity_type == "technology"
        return [
            SimpleNamespace(
                id="entity-1",
                entity_type="technology",
                canonical_name="postgresql",
                mention_count=3,
            )
        ]

    async def fake_get_entity_detail(session, slug, entity_id):
        del session
        assert slug == "intel"
        assert entity_id == "entity-1"
        return SimpleNamespace(
            id="entity-1",
            entity_type="technology",
            canonical_name="postgresql",
            mention_count=3,
            mentions=[
                SimpleNamespace(
                    document_path="docs/architecture.md",
                    document_title="Architecture",
                    chunk_content_snippet="PostgreSQL stores session state.",
                    start_char=12,
                    end_char=22,
                    confidence=0.94,
                    version_number=2,
                )
            ],
            relationships=[
                SimpleNamespace(
                    related_entity="auth service",
                    relationship_type="used_by",
                    direction="incoming",
                    evidence_text="Auth service writes to PostgreSQL.",
                    evidence_document_path="docs/architecture.md",
                    evidence_document_title="Architecture",
                    evidence_heading_path="Storage",
                    evidence_version_number=2,
                    evidence_chunk_id="chunk-42",
                    evidence_start_char=44,
                    evidence_end_char=78,
                )
            ],
        )

    monkeypatch.setattr("datum.api.entities.list_project_entities", fake_list_entities)
    monkeypatch.setattr("datum.api.entities.get_project_entity_detail", fake_get_entity_detail)

    entities = await client.get(
        "/api/v1/projects/intel/entities",
        params={"entity_type": "technology"},
    )
    assert entities.status_code == 200
    assert entities.json()["entities"][0]["canonical_name"] == "postgresql"

    detail = await client.get("/api/v1/projects/intel/entities/entity-1")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["canonical_name"] == "postgresql"
    assert payload["mentions"][0]["document_path"] == "docs/architecture.md"
    assert payload["relationships"][0]["related_entity"] == "auth service"
    assert payload["relationships"][0]["evidence_document_path"] == "docs/architecture.md"
    assert payload["relationships"][0]["evidence_chunk_id"] == "chunk-42"


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
