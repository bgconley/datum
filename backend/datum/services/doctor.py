"""Datum Doctor: integrity checker for the project file cabinet.

Verifies:
- Project manifests parse correctly
- Canonical files match manifest heads
- Version files exist and hash correctly
- No orphan version files
- No stale pending_commits
"""
import logging
from dataclasses import dataclass, field
from pathlib import Path

from datum.services.filesystem import (
    compute_content_hash,
    doc_manifest_dir,
    _legacy_manifest_dir,
    read_manifest,
)

logger = logging.getLogger(__name__)


@dataclass
class DoctorReport:
    project: str
    files_checked: int = 0
    versions_checked: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_healthy(self) -> bool:
        return len(self.errors) == 0


def check_project(project_path: Path) -> DoctorReport:
    """Run all integrity checks on a project."""
    report = DoctorReport(project=project_path.name)

    if not (project_path / "project.yaml").exists():
        report.errors.append("project.yaml missing")
        return report

    # Check all manifests under .piq/ (docs and attachments)
    piq_root = project_path / ".piq"
    if not piq_root.exists():
        return report

    for manifest_path in sorted(piq_root.rglob("manifest.yaml")):
        # Skip the project-level manifest
        if manifest_path.parent == piq_root:
            continue
        _check_document_manifest(project_path, manifest_path, report)

    # Check for legacy manifest layout conflicts
    _check_legacy_layouts(project_path, piq_root, report)

    return report


def _check_document_manifest(
    project_path: Path, manifest_path: Path, report: DoctorReport
):
    try:
        manifest = read_manifest(manifest_path)
    except Exception as e:
        report.errors.append(
            f"Cannot parse manifest: {manifest_path.relative_to(project_path)} ({e})"
        )
        return
    if not manifest:
        report.errors.append(f"Cannot parse manifest: {manifest_path}")
        return

    canonical_path = manifest.get("canonical_path", "")
    manifest_dir = manifest_path.parent

    # Check for stale pending_commit
    if "pending_commit" in manifest:
        report.warnings.append(
            f"Stale pending_commit in {manifest_path.relative_to(project_path)}"
        )

    # Check each branch
    for branch_name, branch_data in manifest.get("branches", {}).items():
        versions = branch_data.get("versions", [])
        known_files = set()

        for v in versions:
            report.versions_checked += 1
            version_file = manifest_dir / v["file"]
            known_files.add(version_file.name)

            # Check version file exists
            if not version_file.exists():
                report.errors.append(
                    f"Version file missing: {v['file']} "
                    f"(doc: {canonical_path}, v{v['version']:03d})"
                )
                continue

            # Check version file hash matches manifest
            actual_hash = compute_content_hash(version_file.read_bytes())
            expected_hash = v.get("content_hash", "")
            if actual_hash != expected_hash:
                report.errors.append(
                    f"Hash mismatch for {v['file']}: "
                    f"expected {expected_hash[:20]}..., got {actual_hash[:20]}..."
                )

        # Check for orphan version files in branch directory
        branch_dir = manifest_dir / branch_name
        if branch_dir.is_dir():
            for f in branch_dir.iterdir():
                if f.is_file() and f.name not in known_files:
                    report.warnings.append(
                        f"Orphan version file: {f.relative_to(project_path)}"
                    )

        # Validate head pointer consistency
        head_str = branch_data.get("head")
        if head_str and versions:
            # head should reference the last version's version_str
            last_version_str = f"v{versions[-1]['version']:03d}"
            if head_str != last_version_str:
                report.errors.append(
                    f"Head pointer mismatch on {branch_name}: "
                    f"head={head_str} but last version is {last_version_str} "
                    f"(doc: {canonical_path})"
                )

    # Check canonical file matches the head version's hash
    report.files_checked += 1
    canonical_full = project_path / canonical_path
    if canonical_full.exists():
        canonical_hash = compute_content_hash(canonical_full.read_bytes())
        for branch_name, branch_data in manifest.get("branches", {}).items():
            head_str = branch_data.get("head")
            versions = branch_data.get("versions", [])
            if not head_str or not versions:
                continue
            # Find the version that head points to (by head_str, not just [-1])
            head_version = None
            for v in versions:
                if f"v{v['version']:03d}" == head_str:
                    head_version = v
                    break
            if head_version:
                head_hash = head_version.get("content_hash", "")
                if canonical_hash != head_hash:
                    report.warnings.append(
                        f"Canonical file differs from manifest head: {canonical_path}"
                    )
            else:
                report.errors.append(
                    f"Head pointer {head_str} references nonexistent version "
                    f"(doc: {canonical_path})"
                )


def _check_legacy_layouts(project_path: Path, piq_root: Path, report: DoctorReport):
    """Detect legacy manifest directories that need migration."""
    for manifest_path in sorted(piq_root.rglob("manifest.yaml")):
        if manifest_path.parent == piq_root:
            continue
        try:
            manifest = read_manifest(manifest_path)
        except Exception:
            continue  # Already reported by _check_document_manifest
        if not manifest:
            continue
        canonical_path = manifest.get("canonical_path", "")
        if not canonical_path:
            continue

        # Check if this manifest dir uses the legacy (stem-only) naming
        manifest_dir = manifest_path.parent
        new_dir = doc_manifest_dir(project_path, canonical_path)
        legacy_dir = _legacy_manifest_dir(project_path, canonical_path)

        if manifest_dir == legacy_dir and manifest_dir != new_dir:
            # This is a legacy layout — check if new dir also exists
            if (new_dir / "manifest.yaml").exists():
                report.errors.append(
                    f"Both legacy ({legacy_dir.name}/) and new ({new_dir.name}/) "
                    f"manifest dirs exist for {canonical_path} — run migration"
                )
            else:
                report.warnings.append(
                    f"Legacy manifest layout for {canonical_path}: "
                    f"{legacy_dir.name}/ should be {new_dir.name}/ — run migration"
                )
