"""Filesystem watcher utilities: path filtering, state computation, debouncing."""
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from datum.services.filesystem import compute_content_hash

IGNORE_PATTERNS = {
    ".piq",
    ".git",
    "__pycache__",
    "node_modules",
}

IGNORE_SUFFIXES = {".tmp", ".swp", ".swo", ".pyc"}

IGNORE_NAMES = {".DS_Store", "Thumbs.db"}


def should_process_path(path: Path) -> bool:
    """Check if a filesystem path should trigger watcher processing."""
    parts = path.parts
    for part in parts:
        if part in IGNORE_PATTERNS:
            return False
    if path.name in IGNORE_NAMES:
        return False
    if path.suffix in IGNORE_SUFFIXES:
        return False
    return True


@dataclass
class FileState:
    path: Path
    content_hash: str
    byte_size: int
    mtime: datetime


def compute_file_state(path: Path) -> Optional[FileState]:
    """Compute the current state of a file for sync comparison."""
    if not path.exists() or not path.is_file():
        return None
    content = path.read_bytes()
    stat = path.stat()
    return FileState(
        path=path,
        content_hash=compute_content_hash(content),
        byte_size=len(content),
        mtime=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
    )
