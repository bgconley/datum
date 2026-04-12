import pytest
from pathlib import Path

from datum.services.filesystem import compute_content_hash, read_manifest
from datum.services.versioning import create_version, get_current_version, VersionInfo


class TestCreateVersion:
    def test_first_version(self, tmp_path):
        """Creating a version for a new document produces v001."""
        project = tmp_path / "my-project"
        project.mkdir()
        (project / ".piq").mkdir()

        canonical = "docs/notes.md"
        content = b"# My Notes\n\nSome content here."
        canonical_path = project / canonical
        canonical_path.parent.mkdir(parents=True, exist_ok=True)
        canonical_path.write_bytes(content)

        info = create_version(
            project_path=project,
            canonical_path=canonical,
            content=content,
            change_source="web",
        )

        assert info.version_number == 1
        assert info.branch == "main"
        assert info.content_hash == compute_content_hash(content)
        # Version file exists on disk
        version_file = project / ".piq" / "docs" / "notes" / "main" / "v001.md"
        assert version_file.exists()
        assert version_file.read_bytes() == content
        # Manifest updated
        manifest = read_manifest(project / ".piq" / "docs" / "notes" / "manifest.yaml")
        assert manifest["branches"]["main"]["head"] == "v001"
        assert len(manifest["branches"]["main"]["versions"]) == 1

    def test_second_version(self, tmp_path):
        """Creating a second version produces v002."""
        project = tmp_path / "my-project"
        project.mkdir()
        (project / ".piq").mkdir()

        canonical = "docs/notes.md"
        canonical_path = project / canonical
        canonical_path.parent.mkdir(parents=True, exist_ok=True)

        # First version
        content_v1 = b"# V1"
        canonical_path.write_bytes(content_v1)
        create_version(project, canonical, content_v1, "web")

        # Second version
        content_v2 = b"# V2 updated"
        canonical_path.write_bytes(content_v2)
        info = create_version(project, canonical, content_v2, "web")

        assert info.version_number == 2
        v2_file = project / ".piq" / "docs" / "notes" / "main" / "v002.md"
        assert v2_file.exists()
        assert v2_file.read_bytes() == content_v2
        manifest = read_manifest(project / ".piq" / "docs" / "notes" / "manifest.yaml")
        assert manifest["branches"]["main"]["head"] == "v002"
        assert len(manifest["branches"]["main"]["versions"]) == 2

    def test_idempotent_same_hash(self, tmp_path):
        """Creating a version with identical content to head is a no-op."""
        project = tmp_path / "my-project"
        project.mkdir()
        (project / ".piq").mkdir()

        canonical = "docs/notes.md"
        canonical_path = project / canonical
        canonical_path.parent.mkdir(parents=True, exist_ok=True)
        content = b"# Same content"
        canonical_path.write_bytes(content)

        info1 = create_version(project, canonical, content, "web")
        info2 = create_version(project, canonical, content, "watcher")

        assert info2 is None  # No new version created

    def test_pending_commit_cleared(self, tmp_path):
        """After successful version creation, no pending_commit in manifest."""
        project = tmp_path / "my-project"
        project.mkdir()
        (project / ".piq").mkdir()

        canonical = "docs/notes.md"
        canonical_path = project / canonical
        canonical_path.parent.mkdir(parents=True, exist_ok=True)
        canonical_path.write_bytes(b"content")

        create_version(project, canonical, b"content", "web")

        manifest = read_manifest(project / ".piq" / "docs" / "notes" / "manifest.yaml")
        assert "pending_commit" not in manifest


class TestGetCurrentVersion:
    def test_no_versions(self, tmp_path):
        project = tmp_path / "my-project"
        project.mkdir()
        (project / ".piq").mkdir()
        result = get_current_version(project, "docs/notes.md")
        assert result is None

    def test_returns_head(self, tmp_path):
        project = tmp_path / "my-project"
        project.mkdir()
        (project / ".piq").mkdir()

        canonical = "docs/notes.md"
        (project / canonical).parent.mkdir(parents=True, exist_ok=True)
        (project / canonical).write_bytes(b"v1")
        create_version(project, canonical, b"v1", "web")
        (project / canonical).write_bytes(b"v2")
        create_version(project, canonical, b"v2", "web")

        info = get_current_version(project, canonical)
        assert info is not None
        assert info.version_number == 2
