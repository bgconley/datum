"""Filesystem watcher entry point.

Monitors the projects root for changes, debounces rapid events,
and queues version creation for changed files.

Run: python -m datum.watcher
"""
import logging
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler, FileSystemEvent
from watchdog.observers import Observer

from datum.config import settings
from datum.services.watcher_utils import should_process_path, compute_file_state
from datum.services.versioning import create_version

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
        path = Path(event.src_path)
        if should_process_path(path):
            self._pending[str(path)] = time.monotonic()
        # For rename/move events, also record dest_path.
        # Editor atomic saves (write tmp -> rename to target) produce move events
        # where src_path is the filtered temp file but dest_path is the real target.
        # Design doc: "treat all relevant events as 'path may have changed'"
        dest = getattr(event, "dest_path", None)
        if dest:
            dest_path = Path(dest)
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

            # Skip project.yaml itself for now (Task 14 adds project metadata versioning)
            if canonical_path == "project.yaml":
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
                # DB catch-up deferred to Task 12 (DB Mirroring)
            except Exception:
                logger.exception(f"Watcher: failed to version {path}")


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
