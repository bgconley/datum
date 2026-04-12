"""Regression tests for legacy manifest layout migration.

Pre-fix manifests were stored under .piq/.../<stem>/ (e.g. .piq/docs/foo/).
Post-fix manifests use .piq/.../<filename.ext>/ (e.g. .piq/docs/foo.md/).

These tests verify that:
- Legacy-only layouts are still readable (GET returns real version/hash)
- GET→PUT round-trip succeeds on legacy data
- Legacy foo.md + new foo.sql do not collide
- Write to legacy path triggers migration to new layout
- Both legacy+new dirs present triggers ManifestLayoutConflictError
"""
import pytest
from pathlib import Path

import yaml

from datum.services.filesystem import (
    atomic_write,
    compute_content_hash,
    read_manifest,
    write_manifest,
    resolve_manifest_dir,
    ManifestLayoutConflictError,
)
from datum.services.versioning import create_version, get_current_version
from datum.services.project_manager import create_project
from datum.services.document_manager import create_document, save_document, get_document


def _create_legacy_manifest(project_path: Path, canonical_path: str, content: bytes):
    """Simulate a pre-fix manifest layout (keyed by stem, not full filename)."""
    rel = Path(canonical_path)
    legacy_dir = project_path / ".piq" / rel.parent / rel.stem
    legacy_dir.mkdir(parents=True, exist_ok=True)

    content_hash = compute_content_hash(content)
    manifest = {
        "document_uid": "doc_legacy_test",
        "canonical_path": canonical_path,
        "branches": {
            "main": {
                "head": "v001",
                "versions": [
                    {
                        "version": 1,
                        "file": f"main/v001{rel.suffix}",
                        "content_hash": content_hash,
                        "created": "2026-04-12T00:00:00+00:00",
                    }
                ],
            }
        },
    }
    write_manifest(legacy_dir / "manifest.yaml", manifest)

    # Write version file
    version_dir = legacy_dir / "main"
    version_dir.mkdir(parents=True, exist_ok=True)
    atomic_write(version_dir / f"v001{rel.suffix}", content)

    # Write canonical file
    canonical_full = project_path / canonical_path
    canonical_full.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(canonical_full, content)


@pytest.fixture
def project(tmp_path):
    create_project(tmp_path, "Legacy Test", "legacy-test")
    return tmp_path / "legacy-test"


class TestLegacyManifestRead:
    def test_get_current_version_reads_legacy(self, project):
        """Legacy manifest is readable via get_current_version."""
        content = b"---\ntitle: Legacy\ntype: plan\n---\n# Legacy doc"
        _create_legacy_manifest(project, "docs/foo.md", content)

        ver = get_current_version(project, "docs/foo.md")
        assert ver is not None
        assert ver.version_number == 1
        assert ver.document_uid == "doc_legacy_test"
        assert ver.content_hash == compute_content_hash(content)

    def test_get_document_returns_real_version(self, project):
        """get_document returns real version/hash from legacy layout."""
        content = b"---\ntitle: Legacy\ntype: plan\n---\n# Legacy doc"
        _create_legacy_manifest(project, "docs/foo.md", content)

        info = get_document(project, "docs/foo.md")
        assert info is not None
        assert info.version == 1
        assert info.content_hash == compute_content_hash(content)
        assert info.document_uid == "doc_legacy_test"


class TestLegacyManifestWrite:
    def test_save_migrates_to_new_layout(self, project):
        """Save on legacy data migrates manifest dir to new layout."""
        content = b"---\ntitle: Legacy\ntype: plan\n---\n# Legacy doc"
        _create_legacy_manifest(project, "docs/foo.md", content)

        # Save triggers migration (for_write=True in resolve_manifest_dir)
        base_hash = compute_content_hash(content)
        full_content = (project / "docs" / "foo.md").read_text()
        modified = full_content.replace("# Legacy doc", "# Updated doc")
        info = save_document(project, "docs/foo.md", modified, base_hash, "web")
        assert info.version == 2

        # New-style dir should now exist, legacy should be gone
        new_dir = project / ".piq" / "docs" / "foo.md"
        legacy_dir = project / ".piq" / "docs" / "foo"
        assert (new_dir / "manifest.yaml").exists()
        assert not legacy_dir.exists()

    def test_get_put_roundtrip_on_legacy_data(self, project):
        """Full GET→PUT round-trip works on legacy layout."""
        content = b"---\ntitle: RT\ntype: plan\n---\n# Round trip"
        _create_legacy_manifest(project, "docs/rt.md", content)

        # GET
        info = get_document(project, "docs/rt.md")
        assert info.version == 1
        full_content = (project / "docs" / "rt.md").read_text()

        # PUT (modifies body)
        modified = full_content.replace("# Round trip", "# Modified")
        info2 = save_document(project, "docs/rt.md", modified, info.content_hash, "web")
        assert info2.version == 2

        # Verify content on disk
        final = (project / "docs" / "rt.md").read_text()
        assert "# Modified" in final
        assert final.count("title: RT") == 1


class TestLegacyNewCoexistence:
    def test_legacy_md_new_sql_no_collision(self, project):
        """Legacy foo.md manifest + new foo.sql must not collide."""
        md_content = b"---\ntitle: MD\ntype: plan\n---\n# Markdown"
        _create_legacy_manifest(project, "docs/foo.md", md_content)

        # Create foo.sql through normal (new-layout) path
        sql_info = create_document(project, "docs/foo.sql", "SQL", "schema", "CREATE TABLE foo;")
        assert sql_info.version == 1

        # foo.md still reads from legacy
        md_ver = get_current_version(project, "docs/foo.md")
        assert md_ver is not None
        assert md_ver.document_uid == "doc_legacy_test"

        # foo.sql has its own UID
        assert sql_info.document_uid != md_ver.document_uid


class TestManifestConflict:
    def test_both_dirs_raises_conflict(self, project):
        """Both legacy and new manifest dirs for same path raises error."""
        content = b"---\ntitle: Dup\ntype: plan\n---\n# Dup"
        _create_legacy_manifest(project, "docs/dup.md", content)

        # Also create new-style dir
        new_dir = project / ".piq" / "docs" / "dup.md"
        new_dir.mkdir(parents=True, exist_ok=True)
        write_manifest(new_dir / "manifest.yaml", {
            "document_uid": "doc_new",
            "canonical_path": "docs/dup.md",
            "branches": {},
        })

        with pytest.raises(ManifestLayoutConflictError):
            resolve_manifest_dir(project, "docs/dup.md", for_write=False)
