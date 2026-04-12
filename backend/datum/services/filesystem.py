"""Filesystem operations: hashing, atomic writes, manifest management.

All filesystem writes follow the design doc's atomic write protocol:
temp file -> fsync -> rename. Manifests are YAML files in .piq/ directories.
"""
import hashlib
import os
import tempfile
import uuid
from datetime import datetime, timezone
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
    for subdir in ["docs", "drafts", "extracted", "records", "operations", "tmp", "project/versions"]:
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


def doc_manifest_dir(project_path: Path, canonical_path: str) -> Path:
    """Get the .piq manifest directory for a document.

    Example: canonical_path="docs/requirements/auth-req.md"
    Returns: project_path/.piq/docs/requirements/auth-req/

    Raises ValueError if canonical_path is absolute or traverses outside the project.
    """
    rel = validate_canonical_path(canonical_path)
    stem = rel.stem  # "auth-req"
    parent = rel.parent  # "docs/requirements"
    return project_path / ".piq" / parent / stem


def generate_uid(prefix: str = "doc") -> str:
    """Generate a stable UID like doc_01ht7x9..."""
    short = uuid.uuid4().hex[:12]
    return f"{prefix}_{short}"
