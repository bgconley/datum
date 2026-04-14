"""Content-addressed blob storage for uploaded attachments."""

from __future__ import annotations

import hashlib
from pathlib import Path

from datum.services.filesystem import atomic_write


def _normalize_extension(extension: str) -> str:
    if not extension:
        return ""
    if not extension.startswith("."):
        return f".{extension.lower()}"
    return extension.lower()


def compute_blob_path(hash_hex: str, extension: str) -> str:
    ext = _normalize_extension(extension)
    return f"{hash_hex[:2]}/{hash_hex[2:4]}/{hash_hex}{ext}"


def store_blob(content: bytes, extension: str, blobs_root: str | Path) -> dict[str, str | int]:
    hash_hex = hashlib.sha256(content).hexdigest()
    content_hash = f"sha256:{hash_hex}"
    relative_path = compute_blob_path(hash_hex, extension)
    absolute_path = Path(blobs_root) / relative_path

    if not absolute_path.exists():
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(absolute_path, content)

    return {
        "content_hash": content_hash,
        "blob_path": relative_path,
        "size_bytes": len(content),
    }
