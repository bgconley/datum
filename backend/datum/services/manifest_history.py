"""Manifest lifecycle history helpers.

The filesystem manifest is the canonical record for version/head transitions.
Postgres `version_head_events` is derived from this history.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid5


def deterministic_document_uid(project_slug: str, canonical_path: str) -> str:
    """Mint a deterministic UUIDv5 for imported manifests missing a UID."""
    return str(uuid5(NAMESPACE_URL, f"datum:{project_slug}:{canonical_path}"))


def ensure_manifest_head_events(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Ensure a manifest has lifecycle history, synthesizing it for legacy data."""
    existing = manifest.get("head_events")
    if isinstance(existing, list):
        return existing

    canonical_path = str(manifest.get("canonical_path", ""))
    deleted_at = manifest.get("deleted_at")
    synthesized: list[dict[str, Any]] = []

    for branch, branch_data in sorted((manifest.get("branches") or {}).items()):
        versions = sorted(
            branch_data.get("versions", []),
            key=lambda item: (
                _coerce_timestamp(item.get("created")) or datetime.min.replace(tzinfo=UTC),
                int(item.get("version", 0)),
            ),
        )
        for index, version in enumerate(versions):
            valid_from = str(version.get("created", ""))
            next_created = (
                str(versions[index + 1].get("created"))
                if index + 1 < len(versions)
                else None
            )
            synthesized.append(
                {
                    "branch": branch,
                    "version": int(version["version"]),
                    "canonical_path": canonical_path,
                    "event_type": "save",
                    "valid_from": valid_from,
                    "valid_to": next_created,
                }
            )

        if versions and deleted_at:
            synthesized[-1]["valid_to"] = deleted_at
            synthesized.append(
                {
                    "branch": branch,
                    "version": int(versions[-1]["version"]),
                    "canonical_path": canonical_path,
                    "event_type": "delete",
                    "valid_from": deleted_at,
                    "valid_to": deleted_at,
                }
            )

    manifest["head_events"] = synthesized
    return synthesized


def record_manifest_save_event(
    manifest: dict[str, Any],
    *,
    branch: str,
    version_number: int,
    canonical_path: str,
    at: datetime,
) -> None:
    """Close the prior head and append a save event for the new head."""
    head_events = ensure_manifest_head_events(manifest)
    timestamp = at.astimezone(UTC).isoformat()
    for event in reversed(head_events):
        if event.get("branch") != branch:
            continue
        if event.get("event_type") != "save":
            continue
        if event.get("valid_to") is None:
            event["valid_to"] = timestamp
            break

    head_events.append(
        {
            "branch": branch,
            "version": version_number,
            "canonical_path": canonical_path,
            "event_type": "save",
            "valid_from": timestamp,
            "valid_to": None,
        }
    )


def record_manifest_delete_event(
    manifest: dict[str, Any],
    *,
    branch: str,
    version_number: int,
    canonical_path: str,
    at: datetime,
) -> None:
    """Close the prior head and append a zero-length delete transition."""
    head_events = ensure_manifest_head_events(manifest)
    timestamp = at.astimezone(UTC).isoformat()
    for event in reversed(head_events):
        if event.get("branch") != branch:
            continue
        if event.get("event_type") != "save":
            continue
        if event.get("canonical_path") != canonical_path:
            continue
        if event.get("valid_to") is None:
            event["valid_to"] = timestamp
            break

    head_events.append(
        {
            "branch": branch,
            "version": version_number,
            "canonical_path": canonical_path,
            "event_type": "delete",
            "valid_from": timestamp,
            "valid_to": timestamp,
        }
    )


def get_manifest_head_version(
    manifest: dict[str, Any],
    *,
    branch: str = "main",
) -> int | None:
    branch_data = (manifest.get("branches") or {}).get(branch) or {}
    head = branch_data.get("head")
    if not isinstance(head, str) or not head.startswith("v"):
        return None
    try:
        return int(head[1:])
    except ValueError:
        return None


def _coerce_timestamp(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
