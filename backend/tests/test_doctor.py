import pytest
from pathlib import Path

from datum.services.project_manager import create_project
from datum.services.document_manager import create_document
from datum.services.doctor import check_project, DoctorReport


class TestDoctor:
    @pytest.fixture
    def project(self, tmp_path):
        create_project(tmp_path, "Test", "test")
        return tmp_path / "test"

    def test_healthy_project(self, project):
        create_document(project, "docs/a.md", "A", "plan", "# A")
        report = check_project(project)
        assert report.is_healthy
        assert report.errors == []

    def test_missing_version_file(self, project):
        create_document(project, "docs/a.md", "A", "plan", "# A")
        # Delete the version file
        v001 = project / ".piq" / "docs" / "a" / "main" / "v001.md"
        v001.unlink()
        report = check_project(project)
        assert not report.is_healthy
        assert any("version file missing" in e.lower() for e in report.errors)

    def test_hash_mismatch(self, project):
        create_document(project, "docs/a.md", "A", "plan", "# A")
        # Corrupt the version file
        v001 = project / ".piq" / "docs" / "a" / "main" / "v001.md"
        v001.write_bytes(b"corrupted content")
        report = check_project(project)
        assert not report.is_healthy
        assert any("hash mismatch" in e.lower() for e in report.errors)

    def test_canonical_manifest_mismatch(self, project):
        create_document(project, "docs/a.md", "A", "plan", "# A")
        # Modify canonical file without creating a version
        (project / "docs" / "a.md").write_bytes(b"modified without version")
        report = check_project(project)
        assert any("canonical file" in w.lower() for w in report.warnings)

    def test_orphan_version_file(self, project):
        create_document(project, "docs/a.md", "A", "plan", "# A")
        # Create an orphan version file
        orphan = project / ".piq" / "docs" / "a" / "main" / "v099.md"
        orphan.write_bytes(b"orphan")
        report = check_project(project)
        assert any("orphan" in w.lower() for w in report.warnings)

    def test_malformed_yaml_does_not_crash(self, project):
        """Finding 3: doctor should report, not crash, on invalid YAML."""
        create_document(project, "docs/a.md", "A", "plan", "# A")
        manifest_path = project / ".piq" / "docs" / "a" / "manifest.yaml"
        manifest_path.write_text("invalid: yaml: [unterminated")
        report = check_project(project)
        assert not report.is_healthy
        assert any("cannot parse manifest" in e.lower() for e in report.errors)

    def test_head_pointer_mismatch(self, project):
        """Finding 4: doctor must detect when head points to wrong version."""
        from datum.services.filesystem import read_manifest, write_manifest
        create_document(project, "docs/a.md", "A", "plan", "# V1")
        # Save V2
        from datum.services.document_manager import save_document
        from datum.services.filesystem import compute_content_hash
        full = (project / "docs" / "a.md").read_text()
        base_hash = compute_content_hash((project / "docs" / "a.md").read_bytes())
        save_document(project, "docs/a.md", full.replace("# V1", "# V2"), base_hash, "web")

        # Corrupt head pointer to point at v001 instead of v002
        manifest_path = project / ".piq" / "docs" / "a" / "manifest.yaml"
        manifest = read_manifest(manifest_path)
        manifest["branches"]["main"]["head"] = "v001"
        write_manifest(manifest_path, manifest)

        report = check_project(project)
        assert not report.is_healthy
        assert any("head pointer mismatch" in e.lower() for e in report.errors)
