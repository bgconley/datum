"""Filesystem watcher entry point.

Monitors the projects root for changes, debounces rapid events,
and queues version creation for changed files.

Run: python -m datum.watcher
"""
import logging
import time
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from datum.config import settings
from datum.services.versioning import create_version
from datum.services.watcher_utils import compute_file_state, should_process_path

logger = logging.getLogger(__name__)

DEBOUNCE_SECONDS = 2.0


class DebouncedHandler(FileSystemEventHandler):
    """Debounces filesystem events and processes stable files."""

    def __init__(self, projects_root: Path):
        self.projects_root = projects_root
        self._pending: dict[str, float] = {}
        self._known_hashes: dict[str, str] = {}

    def on_any_event(self, event: FileSystemEvent):
        if event.is_directory:
            return
        # Record src_path if it passes filtering
        path = Path(str(event.src_path))
        if should_process_path(path):
            self._pending[str(path)] = time.monotonic()
        # For rename/move events, also record dest_path.
        # Editor atomic saves (write tmp -> rename to target) produce move events
        # where src_path is the filtered temp file but dest_path is the real target.
        # Design doc: "treat all relevant events as 'path may have changed'"
        dest = getattr(event, "dest_path", None)
        if dest:
            dest_path = Path(str(dest))
            if should_process_path(dest_path):
                self._pending[str(dest_path)] = time.monotonic()

    def process_settled(self):
        """Process files that have been stable for DEBOUNCE_SECONDS."""
        now = time.monotonic()
        settled = [
            p for p, t in list(self._pending.items())
            if now - t >= DEBOUNCE_SECONDS
        ]
        for path_str in settled:
            del self._pending[path_str]
            path = Path(path_str)
            state = compute_file_state(path)
            if state is None:
                continue  # File was deleted

            # Skip if hash unchanged
            old_hash = self._known_hashes.get(path_str)
            if old_hash == state.content_hash:
                continue

            self._known_hashes[path_str] = state.content_hash

            # Determine project and canonical path
            try:
                rel = path.relative_to(self.projects_root)
            except ValueError:
                continue
            parts = rel.parts
            if len(parts) < 2:
                continue  # Not inside a project

            project_slug = parts[0]
            canonical_path = str(Path(*parts[1:]))
            project_path = self.projects_root / project_slug

            if not (project_path / "project.yaml").exists():
                continue  # Not a valid project

            if canonical_path == "project.yaml":
                from datum.services.project_versioning import (
                    sync_project_yaml_to_db,
                    version_project_yaml,
                )
                new_ver = version_project_yaml(
                    project_path, content=path.read_bytes(), change_source="watcher",
                )
                if new_ver:
                    sync_project_yaml_to_db(project_slug, project_path)
                continue

            logger.info(f"Watcher: versioning {project_slug}/{canonical_path}")
            try:
                content = path.read_bytes()
                version_info = create_version(
                    project_path=project_path,
                    canonical_path=canonical_path,
                    content=content,
                    change_source="watcher",
                )
                if version_info:
                    logger.info(
                        f"  Created v{version_info.version_number:03d} "
                        f"({version_info.content_hash[:20]}...)"
                    )
                    # DB catch-up (best-effort)
                    self._sync_to_db(
                        project_slug, project_path, canonical_path,
                        content, version_info,
                    )
            except Exception:
                logger.exception(f"Watcher: failed to version {path}")

    def _sync_to_db(self, project_slug, project_path, canonical_path, content, version_info):
        """Best-effort DB catch-up after a watcher-created version."""
        try:
            import asyncio

            import frontmatter as fm
            from sqlalchemy import select

            from datum.db import async_session
            from datum.models.core import Project
            from datum.services.db_sync import log_audit_event, sync_document_version_to_db
            from datum.services.filesystem import compute_content_hash

            try:
                post = fm.loads(content.decode())
            except Exception:
                post = fm.Post(content.decode())

            async def _sync():
                async with async_session() as session:
                    result = await session.execute(
                        select(Project).where(Project.slug == project_slug)
                    )
                    project = result.scalar_one_or_none()
                    if not project:
                        return
                    await sync_document_version_to_db(
                        session=session,
                        project_id=project.id,
                        version_info=version_info,
                        canonical_path=canonical_path,
                        title=post.get("title", Path(canonical_path).stem),
                        doc_type=post.get("type", "unknown"),
                        status=post.get("status", "draft"),
                        tags=post.get("tags", []),
                        change_source="watcher",
                        content_hash=compute_content_hash(content),
                        byte_size=len(content),
                        filesystem_path=version_info.version_file,
                    )
                    await log_audit_event(
                        session, "watcher", "version_created",
                        project.id, canonical_path,
                        new_hash=compute_content_hash(content),
                    )
                    await session.commit()

            asyncio.run(_sync())
        except Exception:
            logger.debug("Watcher DB sync failed (database may be unavailable)", exc_info=True)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    projects_root = settings.projects_root
    logger.info(f"Watcher starting: monitoring {projects_root}")

    if not projects_root.exists():
        logger.error(f"Projects root does not exist: {projects_root}")
        return

    handler = DebouncedHandler(projects_root)
    observer = Observer()
    observer.schedule(handler, str(projects_root), recursive=True)
    observer.start()

    try:
        while True:
            handler.process_settled()
            time.sleep(0.5)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
