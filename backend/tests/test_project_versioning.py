import pytest
from pathlib import Path

from datum.services.project_manager import create_project
from datum.services.project_versioning import version_project_yaml, _max_version_number
from datum.services.filesystem import compute_content_hash


@pytest.fixture
def project(tmp_path):
    create_project(tmp_path, "Test", "test")
    return tmp_path / "test"


class TestVersionProjectYaml:
    def test_creates_initial_version(self, tmp_path):
        """version_project_yaml creates v001 for a fresh project.yaml."""
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / ".piq" / "project" / "versions").mkdir(parents=True)
        (proj / "project.yaml").write_bytes(b"name: Test\n")
        result = version_project_yaml(proj)
        assert result == 1
        assert (proj / ".piq" / "project" / "versions" / "v001.yaml").exists()

    def test_idempotent_on_unchanged_content(self, project):
        """Finding 2: no duplicate version for identical content."""
        # v001 already exists from create_project
        assert (project / ".piq" / "project" / "versions" / "v001.yaml").exists()
        result = version_project_yaml(project)
        assert result is None  # Idempotent skip
        # Still only v001
        versions = sorted((project / ".piq" / "project" / "versions").glob("v*.yaml"))
        assert len(versions) == 1

    def test_creates_new_version_on_change(self, project):
        """Changed content creates a new version."""
        (project / "project.yaml").write_bytes(b"name: Updated\n")
        result = version_project_yaml(project, change_source="watcher")
        assert result == 2
        assert (project / ".piq" / "project" / "versions" / "v002.yaml").exists()

    def test_gap_safe_numbering(self, project):
        """Finding 3: numbering uses max version, not count."""
        versions_dir = project / ".piq" / "project" / "versions"
        # Simulate gap: delete v001, create v003 manually
        (versions_dir / "v001.yaml").unlink()
        (versions_dir / "v003.yaml").write_bytes(b"name: V3\n")
        # Now modify project.yaml
        (project / "project.yaml").write_bytes(b"name: V4\n")
        result = version_project_yaml(project)
        assert result == 4  # max(3) + 1, not len([v003]) + 1
        assert (versions_dir / "v004.yaml").exists()


class TestMaxVersionNumber:
    def test_empty_dir(self, tmp_path):
        assert _max_version_number(tmp_path) == 0

    def test_nonexistent_dir(self, tmp_path):
        assert _max_version_number(tmp_path / "missing") == 0

    def test_finds_max_with_gaps(self, tmp_path):
        (tmp_path / "v001.yaml").write_bytes(b"")
        (tmp_path / "v005.yaml").write_bytes(b"")
        (tmp_path / "v003.yaml").write_bytes(b"")
        assert _max_version_number(tmp_path) == 5
