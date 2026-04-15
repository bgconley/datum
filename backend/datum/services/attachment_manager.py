"""Attachment lifecycle management.

Attachments are metadata-first cabinet entries under attachments/.../metadata.yaml.
Original opaque bytes live in the blob store and are retained across move/delete.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from datum.services.filesystem import atomic_write, generate_uid, validate_canonical_path

_ALLOWED_ATTACHMENT_PREFIX = "attachments/"


@dataclass
class AttachmentInfo:
    attachment_uid: str
    filename: str
    content_type: str
    byte_size: int
    content_hash: str
    blob_path: str
    relative_path: str
    created_at: str | None = None


def _validate_attachment_path(relative_path: str) -> str:
    resolved = validate_canonical_path(relative_path)
    normalized_path = resolved.as_posix()
    if not normalized_path.startswith(_ALLOWED_ATTACHMENT_PREFIX):
        raise ValueError(f"Attachment path must be under attachments/, got: {relative_path}")
    if resolved.name != "metadata.yaml":
        raise ValueError("Attachment path must point to metadata.yaml")
    return normalized_path


def _deleted_archive_path(project_path: Path, relative_path: str) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    archived = project_path / ".piq" / "deleted" / f"{relative_path}.{timestamp}"
    archived.parent.mkdir(parents=True, exist_ok=True)
    return archived


def list_attachments(project_path: Path) -> list[AttachmentInfo]:
    attachments_root = project_path / "attachments"
    if not attachments_root.exists():
        return []

    attachments: list[AttachmentInfo] = []
    for metadata_path in sorted(attachments_root.rglob("metadata.yaml")):
        payload = _read_attachment_metadata(metadata_path)
        if payload is None:
            continue
        attachments.append(
            _attachment_info_from_payload(
                payload,
                metadata_path.relative_to(project_path).as_posix(),
            )
        )
    return attachments


def move_attachment(
    project_path: Path,
    relative_path: str,
    new_relative_path: str,
) -> AttachmentInfo:
    normalized_path = _validate_attachment_path(relative_path)
    normalized_new_path = _validate_attachment_path(new_relative_path)

    if normalized_path == normalized_new_path:
        existing = get_attachment(project_path, normalized_path)
        if existing is None:
            raise FileNotFoundError(f"Attachment not found: {normalized_path}")
        return existing

    source_path = project_path / normalized_path
    destination_path = project_path / normalized_new_path
    if not source_path.exists():
        raise FileNotFoundError(f"Attachment not found: {normalized_path}")
    if destination_path.exists():
        raise FileExistsError(f"Attachment already exists: {normalized_new_path}")

    payload = _read_attachment_metadata(source_path)
    if payload is None:
        raise FileNotFoundError(f"Attachment metadata missing: {normalized_path}")
    payload.setdefault("attachment_uid", generate_uid("att"))
    payload.setdefault("created_at", datetime.now(UTC).isoformat())
    payload["canonical_path"] = normalized_new_path
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(destination_path, _dump_metadata(payload))

    archived_path = _deleted_archive_path(project_path, normalized_path)
    archived_payload = dict(payload)
    archived_payload["canonical_path"] = normalized_path
    archived_payload["deleted_at"] = datetime.now(UTC).isoformat()
    atomic_write(archived_path, _dump_metadata(archived_payload))

    source_path.unlink()
    _prune_empty_dirs(source_path.parent, stop_at=project_path / "attachments")
    return _attachment_info_from_payload(payload, normalized_new_path)


def delete_attachment(project_path: Path, relative_path: str) -> str:
    normalized_path = _validate_attachment_path(relative_path)
    source_path = project_path / normalized_path
    if not source_path.exists():
        raise FileNotFoundError(f"Attachment not found: {normalized_path}")

    payload = _read_attachment_metadata(source_path)
    if payload is None:
        raise FileNotFoundError(f"Attachment metadata missing: {normalized_path}")
    payload.setdefault("attachment_uid", generate_uid("att"))
    payload.setdefault("created_at", datetime.now(UTC).isoformat())
    payload["canonical_path"] = normalized_path
    payload["deleted_at"] = datetime.now(UTC).isoformat()

    archived_path = _deleted_archive_path(project_path, normalized_path)
    atomic_write(archived_path, _dump_metadata(payload))
    source_path.unlink()
    _prune_empty_dirs(source_path.parent, stop_at=project_path / "attachments")
    return archived_path.relative_to(project_path).as_posix()


def get_attachment(project_path: Path, relative_path: str) -> AttachmentInfo | None:
    normalized_path = _validate_attachment_path(relative_path)
    metadata_path = project_path / normalized_path
    payload = _read_attachment_metadata(metadata_path)
    if payload is None:
        return None
    return _attachment_info_from_payload(payload, normalized_path)


def _read_attachment_metadata(metadata_path: Path) -> dict[str, Any] | None:
    if not metadata_path.exists():
        return None
    payload = yaml.safe_load(metadata_path.read_text()) or {}
    if not isinstance(payload, dict):
        return None
    return payload


def _attachment_info_from_payload(payload: dict[str, Any], relative_path: str) -> AttachmentInfo:
    return AttachmentInfo(
        attachment_uid=str(payload.get("attachment_uid") or generate_uid("att")),
        filename=str(payload.get("filename", Path(relative_path).parent.name)),
        content_type=str(payload.get("content_type", "application/octet-stream")),
        byte_size=int(payload.get("size_bytes", 0)),
        content_hash=str(payload.get("blob_ref") or payload.get("content_hash") or ""),
        blob_path=str(payload.get("blob_path", "")),
        relative_path=relative_path,
        created_at=str(payload.get("created_at")) if payload.get("created_at") else None,
    )


def _dump_metadata(payload: dict[str, Any]) -> bytes:
    return yaml.safe_dump(payload, sort_keys=False).encode("utf-8")


def _prune_empty_dirs(path: Path, *, stop_at: Path) -> None:
    current = path
    stop_at = stop_at.resolve()
    while True:
        try:
            current_resolved = current.resolve()
        except FileNotFoundError:
            current_resolved = current
        if current_resolved == stop_at or current == current.parent:
            return
        if not current.exists() or not current.is_dir():
            current = current.parent
            continue
        if any(current.iterdir()):
            return
        current.rmdir()
        current = current.parent
