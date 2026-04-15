
from concurrent.futures import ThreadPoolExecutor

import pytest

from datum.services.document_manager import (
    ConflictError,
    create_document,
    delete_document,
    delete_document_folder,
    get_document,
    list_documents,
    move_document,
    rename_document_folder,
    save_document,
)
from datum.services.filesystem import compute_content_hash, read_manifest
from datum.services.project_manager import create_project


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
        assert (
            project / ".piq" / "docs" / "requirements" / "auth.md" / "main" / "v001.md"
        ).exists()

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
        assert (project / ".piq" / "docs" / "a.md" / "main" / "v002.md").exists()

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

    def test_parallel_saves_allow_one_winner_and_one_conflict(self, project):
        create_document(project, "docs/a.md", "A", "plan", "# V1")
        original = (project / "docs" / "a.md").read_text()
        base_hash = compute_content_hash((project / "docs" / "a.md").read_bytes())

        def _save(replacement: str):
            updated = original.replace("# V1", replacement)
            try:
                info = save_document(project, "docs/a.md", updated, base_hash, "web")
                return ("ok", info.version)
            except ConflictError as exc:
                return ("conflict", exc.current_hash)

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(
                executor.map(
                    _save,
                    ("# V2 from writer one", "# V2 from writer two"),
                )
            )

        assert sorted(result[0] for result in outcomes) == ["conflict", "ok"]
        assert any(result == ("ok", 2) for result in outcomes)
        assert get_document(project, "docs/a.md").version == 2


class TestListDocuments:
    def test_lists_documents(self, project):
        create_document(project, "docs/a.md", "A", "plan", "# A")
        create_document(project, "docs/b.md", "B", "requirements", "# B")
        docs = list_documents(project)
        titles = {d.title for d in docs}
        assert titles == {"A", "B"}

    def test_lists_plain_code_documents_without_frontmatter(self, project):
        raw_doc = project / "docs" / "schema.prisma"
        raw_doc.parent.mkdir(parents=True, exist_ok=True)
        raw_doc.write_text("model User {\n  id String @id\n}\n")

        docs = list_documents(project)

        assert any(doc.relative_path == "docs/schema.prisma" for doc in docs)


class TestGenericDocumentHandling:
    def test_get_supports_plain_text_documents_without_frontmatter(self, project):
        raw_doc = project / "docs" / "config.ts"
        raw_doc.parent.mkdir(parents=True, exist_ok=True)
        raw_doc.write_text("export const answer = 42\n")

        info = get_document(project, "docs/config.ts")

        assert info is not None
        assert info.relative_path == "docs/config.ts"
        assert info.title == "Config"
        assert info.doc_type == "reference"

    def test_get_supports_binary_documents(self, project):
        binary_doc = project / "docs" / "diagram.pdf"
        binary_doc.parent.mkdir(parents=True, exist_ok=True)
        binary_doc.write_bytes(b"%PDF-1.4\n%stub\n")

        info = get_document(project, "docs/diagram.pdf")

        assert info is not None
        assert info.relative_path == "docs/diagram.pdf"
        assert info.doc_type == "reference"

    def test_save_plain_text_document_preserves_source_without_frontmatter(self, project):
        raw_doc = project / "docs" / "app.ts"
        raw_doc.parent.mkdir(parents=True, exist_ok=True)
        raw_doc.write_text("export const version = 1\n")
        base_hash = compute_content_hash(raw_doc.read_bytes())

        saved = save_document(
            project,
            "docs/app.ts",
            "export const version = 2\n",
            base_hash,
            "web",
        )

        assert saved.relative_path == "docs/app.ts"
        assert raw_doc.read_text() == "export const version = 2\n"
        assert not raw_doc.read_text().startswith("---\n")


class TestLifecycleSemantics:
    def test_move_records_temporal_head_events(self, project):
        create_document(project, "docs/a.md", "A", "plan", "# A")

        moved = move_document(project, "docs/a.md", "docs/archive/a.md")

        assert moved.relative_path == "docs/archive/a.md"
        manifest = read_manifest(
            project / ".piq" / "docs" / "archive" / "a.md" / "manifest.yaml"
        )
        assert manifest["canonical_path"] == "docs/archive/a.md"
        assert [
            version["version"] for version in manifest["branches"]["main"]["versions"]
        ] == [1, 2]
        assert [event["event_type"] for event in manifest["head_events"]] == [
            "save",
            "save",
            "delete",
        ]
        assert manifest["head_events"][0]["canonical_path"] == "docs/a.md"
        assert manifest["head_events"][0]["valid_to"] is not None
        assert manifest["head_events"][1]["canonical_path"] == "docs/archive/a.md"
        assert manifest["head_events"][1]["valid_to"] is None
        assert manifest["head_events"][2]["canonical_path"] == "docs/a.md"
        assert manifest["head_events"][2]["version"] == 1

    def test_delete_records_delete_head_event(self, project):
        create_document(project, "docs/delete-me.md", "Delete", "plan", "# Delete")

        archived_path = delete_document(project, "docs/delete-me.md")

        assert archived_path.startswith(".piq/deleted/docs/delete-me.md.")
        manifest = read_manifest(project / ".piq" / "docs" / "delete-me.md" / "manifest.yaml")
        assert manifest["deleted_at"] is not None
        assert [event["event_type"] for event in manifest["head_events"]] == ["save", "delete"]
        assert manifest["head_events"][0]["valid_to"] is not None
        assert manifest["head_events"][1]["canonical_path"] == "docs/delete-me.md"
        assert manifest["head_events"][1]["valid_to"] == manifest["head_events"][1]["valid_from"]

    def test_folder_rename_decomposes_into_document_moves(self, project):
        create_document(project, "docs/specs/a.md", "A", "plan", "# A")
        create_document(project, "docs/specs/sub/b.md", "B", "plan", "# B")

        moved = rename_document_folder(project, "docs/specs", "docs/archive/specs")

        moved_paths = {document.relative_path for document in moved}
        assert moved_paths == {"docs/archive/specs/a.md", "docs/archive/specs/sub/b.md"}
        assert get_document(project, "docs/specs/a.md") is None
        assert get_document(project, "docs/archive/specs/a.md") is not None

    def test_folder_delete_decomposes_into_document_deletes(self, project):
        create_document(project, "docs/specs/a.md", "A", "plan", "# A")
        create_document(project, "docs/specs/b.md", "B", "plan", "# B")

        archived = delete_document_folder(project, "docs/specs")

        assert len(archived) == 2
        assert get_document(project, "docs/specs/a.md") is None
        assert not (project / "docs" / "specs").exists()


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

    def test_rejects_traversal_back_into_piq(self, project):
        with pytest.raises(ValueError, match="must be under docs/"):
            create_document(project, "docs/../.piq/pwn.md", "Bad", "plan", "# Bad")

    def test_save_rejects_non_docs_path(self, project):
        with pytest.raises(ValueError, match="must be under docs/"):
            save_document(project, "project.yaml", "# Bad", "sha256:fake", "web")

    def test_save_rejects_traversal_back_into_project_root(self, project):
        with pytest.raises(ValueError, match="must be under docs/"):
            save_document(project, "docs/../escape.md", "# Bad", "sha256:fake", "web")

    def test_get_rejects_non_docs_path(self, project):
        with pytest.raises(ValueError, match="must be under docs/"):
            get_document(project, "project.yaml")

    def test_get_rejects_traversal_back_into_piq(self, project):
        with pytest.raises(ValueError, match="must be under docs/"):
            get_document(project, "docs/../.piq/pwn.md")


class TestDocumentDuplicateGuard:
    def test_rejects_duplicate_path(self, project):
        create_document(project, "docs/a.md", "A", "plan", "# A")
        with pytest.raises(FileExistsError):
            create_document(project, "docs/a.md", "A Again", "plan", "# A Again")


class TestSameStemDifferentExtension:
    """Blocker regression: same-stem files must have separate version histories."""

    def test_separate_versions_and_uids(self, project):
        md_info = create_document(project, "docs/foo.md", "Foo MD", "plan", "# Markdown")
        sql_info = create_document(
            project,
            "docs/foo.sql",
            "Foo SQL",
            "schema",
            "CREATE TABLE foo;",
        )

        assert md_info.document_uid != sql_info.document_uid
        assert md_info.version == 1
        assert sql_info.version == 1

        # Each has its own manifest
        md_manifest = (project / ".piq" / "docs" / "foo.md" / "manifest.yaml")
        sql_manifest = (project / ".piq" / "docs" / "foo.sql" / "manifest.yaml")
        assert md_manifest.exists()
        assert sql_manifest.exists()

        from datum.services.filesystem import read_manifest
        md_data = read_manifest(md_manifest)
        sql_data = read_manifest(sql_manifest)
        assert md_data["document_uid"] != sql_data["document_uid"]
