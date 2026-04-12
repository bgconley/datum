"""Reconciler: authoritative filesystem walk that repairs watcher-missed events.

The reconciler walks the project tree, computes file hashes, compares against
manifest state, and creates versions for anything out of sync. It also resolves
stale pending_commit records.
"""
import logging
from dataclasses import dataclass, field
from pathlib import Path

from datum.services.filesystem import (
    atomic_write,
    compute_content_hash,
    doc_manifest_dir,
    read_manifest,
    write_manifest,
)
from datum.services.versioning import create_version, get_current_version
from datum.services.watcher_utils import should_process_path

logger = logging.getLogger(__name__)

DOCUMENT_EXTENSIONS = {".md", ".sql", ".yaml", ".json", ".toml", ".prisma", ".ts", ".py"}


@dataclass
class ReconcileResult:
    files_scanned: int = 0
    versions_created: int = 0
    pending_commits_resolved: int = 0
    errors: list[str] = field(default_factory=list)


async def reconcile_project(project_path: Path, db_session=None) -> ReconcileResult:
    """Walk a project's filesystem and ensure all docs are versioned and manifests are consistent.

    If db_session is provided, syncs new versions to the database.
    If None, filesystem-only reconciliation (still useful, DB catches up later).
    """
    result = ReconcileResult()

    if not (project_path / "project.yaml").exists():
        result.errors.append(f"Not a valid project: {project_path}")
        return result

    # Phase 1: Resolve any stale pending_commits in manifests
    _resolve_pending_commits(project_path, result)

    # Phase 2: Walk docs/ and attachments/ to ensure every canonical file has a current version.
    # The watcher covers both directories, so the reconciler must too — it is the authority.
    scan_dirs = [project_path / "docs", project_path / "attachments"]
    for scan_dir in scan_dirs:
        if not scan_dir.exists():
            continue
        for file_path in sorted(scan_dir.rglob("*")):
            if not file_path.is_file():
                continue
            if file_path.suffix not in DOCUMENT_EXTENSIONS:
                continue
            if not should_process_path(file_path):
                continue

            result.files_scanned += 1
            canonical_path = str(file_path.relative_to(project_path))

            try:
                content = file_path.read_bytes()
                content_hash = compute_content_hash(content)

                current = get_current_version(project_path, canonical_path)
                if current and current.content_hash == content_hash:
                    continue  # Up to date

                # File is new or modified — create a version
                version_info = create_version(
                    project_path=project_path,
                    canonical_path=canonical_path,
                    content=content,
                    change_source="reconciler",
                )
                if version_info:
                    result.versions_created += 1
                    logger.info(
                        f"Reconciler: created v{version_info.version_number:03d} "
                        f"for {canonical_path}"
                    )
                    # DB catch-up if session provided
                    if db_session:
                        try:
                            import frontmatter as fm
                            from datum.services.db_sync import (
                                sync_document_version_to_db,
                                log_audit_event,
                            )
                            from sqlalchemy import select
                            from datum.models.core import Project

                            proj_result = await db_session.execute(
                                select(Project).where(
                                    Project.filesystem_path == str(project_path)
                                )
                            )
                            project = proj_result.scalar_one_or_none()
                            if project:
                                try:
                                    post = fm.loads(content.decode())
                                except Exception:
                                    post = fm.Post(content.decode())
                                await sync_document_version_to_db(
                                    session=db_session,
                                    project_id=project.id,
                                    version_info=version_info,
                                    canonical_path=canonical_path,
                                    title=post.get("title", file_path.stem),
                                    doc_type=post.get("type", "unknown"),
                                    status=post.get("status", "draft"),
                                    tags=post.get("tags", []),
                                    change_source="reconciler",
                                    content_hash=content_hash,
                                    byte_size=len(content),
                                    filesystem_path=version_info.version_file,
                                )
                                await log_audit_event(
                                    db_session, "reconciler", "version_created",
                                    project.id, canonical_path,
                                    new_hash=content_hash,
                                )
                        except Exception:
                            logger.debug(
                                "Reconciler DB sync failed for %s", canonical_path,
                                exc_info=True,
                            )
            except Exception as e:
                result.errors.append(f"{canonical_path}: {e}")
                logger.exception(f"Reconciler error: {canonical_path}")

    return result


def _resolve_pending_commits(project_path: Path, result: ReconcileResult):
    """Find and resolve stale pending_commit records in all manifests.

    Handles all crash recovery states from design doc Section 5:
    - pending_commit exists, no version file: crash before step f. Clear pending_commit.
    - pending_commit exists, version file exists, canonical unchanged: crash between f and h.
      Complete the commit: rename canonical from version content, advance manifest.
    - pending_commit exists, version file + canonical both have new content: crash between h and j.
      Advance manifest to match.
    - pending_commit exists, version file exists, no canonical file: new doc, crash before h.
      Complete by writing canonical from version file.
    """
    # Scan all .piq subdirectories for stale pending_commits — not just docs/.
    # Attachments also use the pending_commit protocol and need crash recovery.
    piq_root = project_path / ".piq"
    if not piq_root.exists():
        return

    for manifest_path in piq_root.rglob("manifest.yaml"):
        manifest = read_manifest(manifest_path)
        pending = manifest.get("pending_commit")
        if not pending:
            continue

        logger.info(f"Reconciler: resolving pending_commit in {manifest_path}")
        version_file = manifest_path.parent / pending.get("file", "")
        canonical_file = project_path / pending.get("canonical_path", "")
        expected_hash = pending.get("content_hash", "")
        branch = pending.get("branch", "main")

        resolved = False

        if not version_file.exists():
            # Crash before step f: version file never written. Discard.
            logger.info("  State: no version file. Discarding pending_commit.")
            resolved = True

        elif version_file.exists():
            version_content = version_file.read_bytes()
            version_hash = compute_content_hash(version_content)

            if not canonical_file.exists():
                # New document, crash before canonical write. Write canonical from version.
                logger.info("  State: version exists, no canonical. Writing canonical.")
                canonical_file.parent.mkdir(parents=True, exist_ok=True)
                atomic_write(canonical_file, version_content)
                resolved = True

            elif canonical_file.exists():
                canonical_hash = compute_content_hash(canonical_file.read_bytes())

                if canonical_hash != expected_hash and version_hash == expected_hash:
                    # Crash between f and h: version file has new content, canonical is old.
                    logger.info("  State: version is new, canonical is old. Completing rename.")
                    atomic_write(canonical_file, version_content)
                    resolved = True

                elif canonical_hash == expected_hash:
                    # Crash between h and j: both files have new content, manifest not advanced.
                    logger.info("  State: canonical updated, manifest not advanced. Completing.")
                    resolved = True

                else:
                    # Unexpected state — canonical has content that matches neither old nor new.
                    logger.warning("  State: unexpected hashes. Advancing manifest from version file.")
                    resolved = True

            # Advance manifest if we're resolving a commit that produced a version file
            if resolved and version_hash == expected_hash:
                branch_data = manifest.get("branches", {}).get(
                    branch, {"head": None, "versions": []}
                )
                existing_versions = {v["version"] for v in branch_data["versions"]}
                if pending["version"] not in existing_versions:
                    branch_data["versions"].append({
                        "version": pending["version"],
                        "file": pending["file"],
                        "content_hash": expected_hash,
                        "created": pending.get("started", ""),
                        "note": "recovered by reconciler",
                    })
                    branch_data["head"] = f"v{pending['version']:03d}"
                    manifest.setdefault("branches", {})[branch] = branch_data

        # Clear pending_commit only after recovery actions are complete
        del manifest["pending_commit"]
        write_manifest(manifest_path, manifest)
        result.pending_commits_resolved += 1
