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
    _legacy_manifest_dir,
    compute_content_hash,
    doc_manifest_dir,
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


def check_blob_refs(refs: list[dict], blobs_root: str | Path) -> list[str]:
    """Verify blob references point to existing files."""
    root = Path(blobs_root)
    errors: list[str] = []
    for ref in refs:
        blob_path = ref.get("blob_path")
        if not blob_path:
            continue
        if not (root / blob_path).exists():
            errors.append(
                f"Missing blob: {blob_path} (referenced by {ref.get('document', '?')})"
            )
    return errors


def check_curated_records(records: list[dict], project_root: str | Path) -> list[str]:
    """Verify curated record files referenced by DB-like rows exist on disk."""
    root = Path(project_root)
    errors: list[str] = []
    for record in records:
        record_path = record.get("canonical_record_path")
        if not record_path:
            continue
        if not (root / record_path).exists():
            errors.append(
                f"Missing curated record: {record_path} (title: {record.get('title', '?')})"
            )
    return errors


async def full_check(
    session,
    *,
    project_id,
    project_root: str | Path,
    blobs_root: str | Path,
) -> dict[str, object]:
    """Run the full doctor suite against filesystem, blobs, and DB-derived records."""
    from sqlalchemy import text

    from datum.services.blob_gc import scan_attachment_metadata

    project_path = Path(project_root)
    report = check_project(project_path)
    errors = list(report.errors)
    warnings = list(report.warnings)

    errors.extend(check_blob_refs(scan_attachment_metadata(project_path), blobs_root))

    curated_result = await session.execute(
        text(
            """
            SELECT canonical_record_path, title
            FROM decisions
            WHERE project_id = :project_id
              AND curation_status = 'accepted'
              AND canonical_record_path IS NOT NULL
            UNION ALL
            SELECT canonical_record_path, title
            FROM requirements
            WHERE project_id = :project_id
              AND curation_status = 'accepted'
              AND canonical_record_path IS NOT NULL
            """
        ),
        {"project_id": project_id},
    )
    curated_records = [
        {"canonical_record_path": row[0], "title": row[1]}
        for row in curated_result.fetchall()
    ]
    errors.extend(check_curated_records(curated_records, project_path))

    stale_chunk_result = await session.execute(
        text(
            """
            SELECT COUNT(*)
            FROM document_chunks dc
            JOIN document_versions dv ON dv.id = dc.version_id
            JOIN documents d ON d.id = dv.document_id
            WHERE d.project_id = :project_id
              AND dv.id != d.current_version_id
            """
        ),
        {"project_id": project_id},
    )
    stale_chunk_count = int(stale_chunk_result.scalar() or 0)
    if stale_chunk_count > 0:
        warnings.append(
            f"{stale_chunk_count} chunks reference non-current document versions"
        )

    return {
        "errors": errors,
        "warnings": warnings,
        "is_healthy": len(errors) == 0,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "files_checked": report.files_checked,
        "versions_checked": report.versions_checked,
    }


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
