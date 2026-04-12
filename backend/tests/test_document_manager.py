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
        # save_document expects full file content (frontmatter included) for round-trip fidelity
        full_content = (project / "docs" / "a.md").read_text()
        base_hash = compute_content_hash((project / "docs" / "a.md").read_bytes())

        modified = full_content.replace("# V1", "# V2 updated")
        info = save_document(
            project_path=project,
            relative_path="docs/a.md",
            content=modified,
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
        full_content = (project / "docs" / "a.md").read_text()
        base_hash = compute_content_hash((project / "docs" / "a.md").read_bytes())
        info = save_document(project, "docs/a.md", full_content, base_hash, "web")
        assert info.version == 1  # No new version

    def test_save_missing_document_raises(self, project):
        """Finding 3: save on nonexistent file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            save_document(project, "docs/missing.md", "# Content", "sha256:fake", "web")


class TestListDocuments:
    def test_lists_documents(self, project):
        create_document(project, "docs/a.md", "A", "plan", "# A")
        create_document(project, "docs/b.md", "B", "requirements", "# B")
        docs = list_documents(project)
        titles = {d.title for d in docs}
        assert titles == {"A", "B"}


class TestDocumentPathEnforcement:
    """Finding 1: documents must live under docs/."""

    def test_rejects_project_yaml_path(self, project):
        with pytest.raises(ValueError, match="must be under docs/"):
            create_document(project, "project.yaml", "Bad", "plan", "# Bad")

    def test_rejects_attachments_path(self, project):
        with pytest.raises(ValueError, match="must be under docs/"):
            create_document(project, "attachments/not-a-doc.md", "Bad", "plan", "# Bad")

    def test_rejects_piq_path(self, project):
        with pytest.raises(ValueError, match="must be under docs/"):
            create_document(project, ".piq/records/bad.yaml", "Bad", "plan", "# Bad")

    def test_rejects_bare_root_path(self, project):
        with pytest.raises(ValueError, match="must be under docs/"):
            create_document(project, "escape.md", "Bad", "plan", "# Bad")

    def test_save_rejects_non_docs_path(self, project):
        with pytest.raises(ValueError, match="must be under docs/"):
            save_document(project, "project.yaml", "# Bad", "sha256:fake", "web")

    def test_get_rejects_non_docs_path(self, project):
        with pytest.raises(ValueError, match="must be under docs/"):
            get_document(project, "project.yaml")


class TestDocumentDuplicateGuard:
    """Finding 4: create_document must reject existing paths."""

    def test_rejects_duplicate_path(self, project):
        create_document(project, "docs/a.md", "A", "plan", "# A")
        with pytest.raises(FileExistsError):
            create_document(project, "docs/a.md", "A Again", "plan", "# A Again")
