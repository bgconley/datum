"""Project metadata versioning — shared logic for project.yaml versioning.

Used by project_manager (on create), watcher (on external edit), and
reconciler (on authoritative walk). Provides hash-based idempotency,
max-based version numbering (gap-safe), and optional DB sync.
"""
import logging
import re
from pathlib import Path

from datum.services.filesystem import atomic_write, compute_content_hash

logger = logging.getLogger(__name__)

_VERSION_RE = re.compile(r"^v(\d+)\.yaml$")


def _max_version_number(versions_dir: Path) -> int:
    """Find the highest version number in a versions directory. Returns 0 if empty."""
    max_num = 0
    if versions_dir.exists():
        for f in versions_dir.iterdir():
            m = _VERSION_RE.match(f.name)
            if m:
                max_num = max(max_num, int(m.group(1)))
    return max_num


def _latest_version_hash(versions_dir: Path) -> str | None:
    """Get the content hash of the highest-numbered version file. None if no versions."""
    max_num = _max_version_number(versions_dir)
    if max_num == 0:
        return None
    latest = versions_dir / f"v{max_num:03d}.yaml"
    if latest.exists():
        return compute_content_hash(latest.read_bytes())
    return None


def version_project_yaml(
    project_path: Path,
    content: bytes | None = None,
    change_source: str = "system",
) -> int | None:
    """Create a new version of project.yaml if content has changed.

    Returns the new version number, or None if content is unchanged (idempotent skip).
    Reads project.yaml from disk if content is not provided.
    """
    project_yaml_path = project_path / "project.yaml"
    if content is None:
        if not project_yaml_path.exists():
            return None
        content = project_yaml_path.read_bytes()

    versions_dir = project_path / ".piq" / "project" / "versions"
    versions_dir.mkdir(parents=True, exist_ok=True)

    content_hash = compute_content_hash(content)

    # Idempotency: skip if content hash matches latest version
    latest_hash = _latest_version_hash(versions_dir)
    if latest_hash == content_hash:
        return None

    # Gap-safe numbering: use max existing version number + 1
    next_num = _max_version_number(versions_dir) + 1
    version_file = versions_dir / f"v{next_num:03d}.yaml"
    atomic_write(version_file, content)

    logger.info(f"Versioned project.yaml as v{next_num:03d} (source: {change_source})")
    return next_num


def sync_project_yaml_to_db(project_slug: str, project_path: Path):
    """Best-effort DB sync after project.yaml version creation."""
    try:
        import asyncio

        import yaml

        from datum.db import async_session
        from datum.services.db_sync import log_audit_event, sync_project_to_db

        project_yaml = project_path / "project.yaml"
        content = project_yaml.read_bytes()
        data = yaml.safe_load(content)

        async def _sync():
            async with async_session() as session:
                project_db_id = await sync_project_to_db(
                    session=session,
                    uid=data.get("uid", ""),
                    slug=data.get("slug", project_slug),
                    name=data.get("name", project_slug),
                    filesystem_path=str(project_path),
                    project_yaml_hash=compute_content_hash(content),
                    description=data.get("description"),
                    tags=data.get("tags"),
                )
                await log_audit_event(
                    session, "system", "project_metadata_updated",
                    project_db_id, "project.yaml",
                    new_hash=compute_content_hash(content),
                )

        asyncio.run(_sync())
    except Exception:
        logger.debug("Project metadata DB sync failed (database may be unavailable)", exc_info=True)
