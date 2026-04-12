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

from datum.services.filesystem import compute_content_hash, doc_manifest_dir, read_manifest

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

    return report


def _check_document_manifest(
    project_path: Path, manifest_path: Path, report: DoctorReport
):
    manifest = read_manifest(manifest_path)
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

    # Check canonical file matches head
    report.files_checked += 1
    canonical_full = project_path / canonical_path
    if canonical_full.exists():
        canonical_hash = compute_content_hash(canonical_full.read_bytes())
        for branch_data in manifest.get("branches", {}).values():
            versions = branch_data.get("versions", [])
            if versions:
                head_hash = versions[-1].get("content_hash", "")
                if canonical_hash != head_hash:
                    report.warnings.append(
                        f"Canonical file differs from manifest head: {canonical_path}"
                    )
