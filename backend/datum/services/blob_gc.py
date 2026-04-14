"""Blob garbage collection using mark-sweep-quarantine-purge semantics."""

from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


def scan_disk_blobs(blobs_root: str | Path) -> set[str]:
    root = Path(blobs_root)
    if not root.exists():
        return set()

    blobs: set[str] = set()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.name.endswith(".tmp"):
            continue
        blobs.add(path.relative_to(root).as_posix())
    return blobs


def scan_attachment_metadata(projects_root: str | Path) -> list[dict[str, str]]:
    root = Path(projects_root)
    if not root.exists():
        return []

    results: list[dict[str, str]] = []
    for metadata_file in root.rglob("attachments/*/metadata.yaml"):
        try:
            payload = yaml.safe_load(metadata_file.read_text())
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        blob_path = payload.get("blob_path")
        if not blob_path:
            continue
        results.append(
            {
                "blob_path": str(blob_path),
                "document": metadata_file.relative_to(root).as_posix(),
            }
        )
    return results


def scan_referenced_blobs(projects_root: str | Path) -> set[str]:
    return {item["blob_path"] for item in scan_attachment_metadata(projects_root)}


def find_orphan_blobs(referenced: set[str], on_disk: set[str]) -> set[str]:
    return on_disk - referenced


def quarantine_blobs(
    orphans: set[str],
    blobs_root: str | Path,
    quarantine_root: str | Path,
) -> int:
    blob_root_path = Path(blobs_root)
    quarantine_path = Path(quarantine_root)
    moved = 0

    for relative_path in sorted(orphans):
        source = blob_root_path / relative_path
        if not source.exists():
            continue
        destination = quarantine_path / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        moved += 1
        logger.info("quarantined blob %s", relative_path)

    return moved


def purge_quarantine(quarantine_root: str | Path, min_age_days: int = 30) -> int:
    root = Path(quarantine_root)
    if not root.exists():
        return 0

    cutoff = time.time() - (min_age_days * 86400)
    deleted = 0
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.stat().st_mtime >= cutoff:
            continue
        path.unlink()
        deleted += 1
        logger.info("purged quarantined blob %s", path)
    return deleted
