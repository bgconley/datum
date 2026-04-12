import pytest
from pathlib import Path

from datum.services.project_manager import create_project
from datum.services.document_manager import create_document
from datum.services.reconciler import reconcile_project, ReconcileResult
from datum.services.filesystem import read_manifest, write_manifest


class TestReconciler:
    @pytest.fixture
    def project(self, tmp_path):
        create_project(tmp_path, "Test", "test")
        return tmp_path / "test"

    @pytest.mark.asyncio
    async def test_no_changes(self, project):
        create_document(project, "docs/a.md", "A", "plan", "# A")
        result = await reconcile_project(project)
        assert result.files_scanned > 0
        assert result.versions_created == 0

    @pytest.mark.asyncio
    async def test_detects_new_unversioned_file(self, project):
        # Manually create a file without going through create_document
        (project / "docs").mkdir(exist_ok=True)
        (project / "docs" / "manual.md").write_text("---\ntitle: Manual\ntype: plan\n---\n# Manual")
        result = await reconcile_project(project)
        assert result.versions_created == 1
        # Manifest should now exist
        manifest = read_manifest(project / ".piq" / "docs" / "manual" / "manifest.yaml")
        assert manifest["branches"]["main"]["head"] == "v001"

    @pytest.mark.asyncio
    async def test_detects_modified_file(self, project):
        create_document(project, "docs/a.md", "A", "plan", "# V1")
        # Directly overwrite the canonical file (simulating external edit)
        (project / "docs" / "a.md").write_text("---\ntitle: A\ntype: plan\n---\n# V2 modified")
        result = await reconcile_project(project)
        assert result.versions_created == 1
        manifest = read_manifest(project / ".piq" / "docs" / "a" / "manifest.yaml")
        assert manifest["branches"]["main"]["head"] == "v002"

    @pytest.mark.asyncio
    async def test_skips_unchanged(self, project):
        create_document(project, "docs/a.md", "A", "plan", "# Same")
        result = await reconcile_project(project)
        assert result.versions_created == 0

    @pytest.mark.asyncio
    async def test_handles_pending_commit_cleanup(self, project):
        create_document(project, "docs/a.md", "A", "plan", "# A")
        # Manually inject a stale pending_commit with no version file
        manifest_path = project / ".piq" / "docs" / "a" / "manifest.yaml"
        manifest = read_manifest(manifest_path)
        manifest["pending_commit"] = {
            "version": 99,
            "branch": "main",
            "file": "main/v099.md",
            "content_hash": "sha256:fake",
            "canonical_path": "docs/a.md",
        }
        write_manifest(manifest_path, manifest)

        result = await reconcile_project(project)
        assert result.pending_commits_resolved > 0
        manifest = read_manifest(manifest_path)
        assert "pending_commit" not in manifest
