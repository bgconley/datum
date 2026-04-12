import pytest
from pathlib import Path

from datum.services.project_manager import create_project
from datum.services.document_manager import (
    create_document,
    save_document,
    get_document,
    list_documents,
    DocumentInfo,
    ConflictError,
)
from datum.services.filesystem import compute_content_hash


@pytest.fixture
def project(tmp_path):
    create_project(tmp_path, "Test Project", "test-project")
    return tmp_path / "test-project"


class TestCreateDocument:
    def test_creates_file_and_version(self, project):
        info = create_document(
            project_path=project,
            relative_path="docs/requirements/auth.md",
            title="Auth Requirements",
            doc_type="requirements",
            content="# Auth Requirements\n\nInitial content.",
            tags=["auth"],
        )
        assert info.title == "Auth Requirements"
        assert info.version == 1
        assert (project / "docs" / "requirements" / "auth.md").exists()
        # Version file exists
        assert (project / ".piq" / "docs" / "requirements" / "auth" / "main" / "v001.md").exists()

    def test_frontmatter_written(self, project):
        create_document(
            project_path=project,
            relative_path="docs/notes.md",
            title="Notes",
            doc_type="brainstorm",
            content="# Notes",
            tags=["misc"],
        )
        raw = (project / "docs" / "notes.md").read_text()
        assert "title: Notes" in raw
        assert "type: brainstorm" in raw


class TestSaveDocument:
    def test_save_creates_new_version(self, project):
        create_document(project, "docs/a.md", "A", "plan", "# V1")
        content_v1 = (project / "docs" / "a.md").read_bytes()
        base_hash = compute_content_hash(content_v1)

        info = save_document(
            project_path=project,
            relative_path="docs/a.md",
            content="# V2 updated",
            base_hash=base_hash,
            change_source="web",
        )
        assert info.version == 2
        assert (project / ".piq" / "docs" / "a" / "main" / "v002.md").exists()

    def test_save_conflict(self, project):
        create_document(project, "docs/a.md", "A", "plan", "# V1")
        wrong_hash = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
        with pytest.raises(ConflictError):
            save_document(project, "docs/a.md", "# V2", wrong_hash, "web")

    def test_save_idempotent(self, project):
        create_document(project, "docs/a.md", "A", "plan", "# Same")
        content = (project / "docs" / "a.md").read_bytes()
        base_hash = compute_content_hash(content)
        info = save_document(project, "docs/a.md", "# Same", base_hash, "web")
        assert info.version == 1  # No new version


class TestListDocuments:
    def test_lists_documents(self, project):
        create_document(project, "docs/a.md", "A", "plan", "# A")
        create_document(project, "docs/b.md", "B", "requirements", "# B")
        docs = list_documents(project)
        titles = {d.title for d in docs}
        assert titles == {"A", "B"}
