"""Filesystem operations: hashing, atomic writes, manifest management.

All filesystem writes follow the design doc's atomic write protocol:
temp file -> fsync -> rename. Manifests are YAML files in .piq/ directories.
"""
import hashlib
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

import yaml


def compute_content_hash(content: bytes) -> str:
    """Compute sha256 hash of content, prefixed with 'sha256:'."""
    digest = hashlib.sha256(content).hexdigest()
    return f"sha256:{digest}"


def atomic_write(path: Path, content: bytes) -> None:
    """Write content to path atomically: temp file -> fsync -> rename.

    Ensures no half-written files appear in the cabinet.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    try:
        os.write(fd, content)
        os.fsync(fd)
        os.close(fd)
        fd = -1  # Mark as closed
        os.rename(tmp_path, path)
        # fsync parent directory to ensure rename is durable
        dir_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except BaseException:
        if fd >= 0:
            os.close(fd)
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def read_manifest(manifest_path: Path) -> dict[str, Any]:
    """Read a YAML manifest file. Returns empty dict if file doesn't exist."""
    if not manifest_path.exists():
        return {}
    return yaml.safe_load(manifest_path.read_text()) or {}


def write_manifest(manifest_path: Path, data: dict[str, Any]) -> None:
    """Write a YAML manifest atomically."""
    content = yaml.dump(data, default_flow_style=False, sort_keys=False).encode()
    atomic_write(manifest_path, content)


def ensure_piq_structure(project_path: Path) -> None:
    """Create the .piq/ directory structure for a project if it doesn't exist."""
    piq = project_path / ".piq"
    subdirs = [
        "docs",
        "drafts",
        "extracted",
        "records",
        "operations",
        "tmp",
        "project/versions",
    ]
    for subdir in subdirs:
        (piq / subdir).mkdir(parents=True, exist_ok=True)


def validate_canonical_path(canonical_path: str) -> Path:
    """Validate that a canonical path is relative and doesn't escape project boundaries.

    Raises ValueError if the path is absolute or contains traversal components.
    """
    rel = Path(canonical_path)
    if rel.is_absolute():
        raise ValueError(f"canonical_path must be relative, got: {canonical_path}")
    # Resolve ".." and check the result stays relative
    try:
        resolved = Path(os.path.normpath(canonical_path))
    except (ValueError, OSError) as e:
        raise ValueError(f"Invalid canonical_path: {canonical_path}") from e
    if resolved.is_absolute() or str(resolved).startswith(".."):
        raise ValueError(f"canonical_path escapes project boundary: {canonical_path}")
    return resolved


class ManifestLayoutConflictError(Exception):
    """Raised when both legacy and new manifest dirs exist for the same canonical path."""
    def __init__(self, canonical_path: str, legacy_dir: Path, new_dir: Path):
        self.canonical_path = canonical_path
        self.legacy_dir = legacy_dir
        self.new_dir = new_dir
        super().__init__(
            f"Both legacy ({legacy_dir.name}/) and new ({new_dir.name}/) manifest dirs "
            f"exist for {canonical_path}. Run datum doctor or migration to resolve."
        )


def doc_manifest_dir(project_path: Path, canonical_path: str) -> Path:
    """Get the canonical .piq manifest directory for a document.

    Uses the full filename (including extension) as the directory name to avoid
    collisions between same-stem files with different extensions (e.g. foo.md
    and foo.sql must have separate manifests and version histories).

    Example: canonical_path="docs/requirements/auth-req.md"
    Returns: project_path/.piq/docs/requirements/auth-req.md/

    Raises ValueError if canonical_path is absolute or traverses outside the project.
    """
    rel = validate_canonical_path(canonical_path)
    name = rel.name  # "auth-req.md" (full filename with extension)
    parent = rel.parent  # "docs/requirements"
    return project_path / ".piq" / parent / name


def _legacy_manifest_dir(project_path: Path, canonical_path: str) -> Path:
    """Get the legacy (pre-fix) manifest directory path keyed by stem only."""
    rel = validate_canonical_path(canonical_path)
    return project_path / ".piq" / rel.parent / rel.stem


def resolve_manifest_dir(
    project_path: Path, canonical_path: str, for_write: bool = False
) -> Path:
    """Resolve the correct manifest directory, handling legacy layouts.

    - If the new-style dir (keyed by full filename) exists, use it.
    - If only the legacy dir (keyed by stem) exists AND its manifest's
      canonical_path matches, use it. On write paths, migrate it first.
    - If both exist for the same canonical_path, raise ManifestLayoutConflictError.
    - If neither exists, return the new-style path (for initial creation).
    """
    new_dir = doc_manifest_dir(project_path, canonical_path)
    legacy_dir = _legacy_manifest_dir(project_path, canonical_path)

    new_exists = (new_dir / "manifest.yaml").exists()
    legacy_exists = (legacy_dir / "manifest.yaml").exists() and legacy_dir != new_dir

    if new_exists and legacy_exists:
        # Both exist — check if legacy actually belongs to this canonical_path
        legacy_manifest = read_manifest(legacy_dir / "manifest.yaml")
        if legacy_manifest.get("canonical_path") == canonical_path:
            raise ManifestLayoutConflictError(canonical_path, legacy_dir, new_dir)
        # Legacy belongs to a different file (e.g. foo.sql vs foo.md) — use new
        return new_dir

    if new_exists:
        return new_dir

    if legacy_exists:
        # Verify the legacy manifest actually belongs to this canonical_path
        legacy_manifest = read_manifest(legacy_dir / "manifest.yaml")
        if legacy_manifest.get("canonical_path") != canonical_path:
            # Legacy dir belongs to a different file — return new path for creation
            return new_dir

        if for_write:
            # Migrate: atomic rename legacy dir to new dir
            _migrate_legacy_manifest(legacy_dir, new_dir)
            return new_dir
        else:
            # Read from legacy location without migrating
            return legacy_dir

    # Neither exists — return new-style path for initial creation
    return new_dir


def _migrate_legacy_manifest(legacy_dir: Path, new_dir: Path) -> None:
    """Atomically migrate a legacy manifest directory to the new layout."""
    import logging
    import shutil
    logger = logging.getLogger(__name__)

    new_dir.parent.mkdir(parents=True, exist_ok=True)
    # Use shutil.move for cross-device safety (ZFS datasets could differ)
    shutil.move(str(legacy_dir), str(new_dir))
    logger.info(f"Migrated legacy manifest: {legacy_dir.name}/ -> {new_dir.name}/")


def generate_uid(prefix: str = "doc") -> str:
    """Generate a stable UID like doc_01ht7x9..."""
    short = uuid.uuid4().hex[:12]
    return f"{prefix}_{short}"
