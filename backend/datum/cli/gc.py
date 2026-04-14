"""CLI for blob garbage collection."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from datum.config import settings
from datum.services.blob_gc import (
    find_orphan_blobs,
    purge_quarantine,
    quarantine_blobs,
    scan_disk_blobs,
    scan_referenced_blobs,
)


def main(argv: Sequence[str] | None = None, *, prog: str = "datum-gc") -> None:
    parser = argparse.ArgumentParser(prog=prog, description="Blob garbage collection")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="find and quarantine orphan blobs")
    run_parser.add_argument("--purge", action="store_true", help="purge old quarantined blobs")
    run_parser.add_argument("--min-age-days", type=int, default=30)

    subparsers.add_parser("stats", help="show blob store statistics")

    args = parser.parse_args(list(argv) if argv is not None else None)
    if not args.command:
        parser.print_help()
        return

    on_disk = scan_disk_blobs(settings.blobs_root)
    if args.command == "stats":
        print(f"Total blobs: {len(on_disk)}")
        return

    referenced = scan_referenced_blobs(settings.projects_root)
    orphans = find_orphan_blobs(referenced, on_disk)
    print(f"Blobs on disk: {len(on_disk)}")
    print(f"Referenced blobs: {len(referenced)}")
    print(f"Orphan blobs: {len(orphans)}")
    if orphans:
        moved = quarantine_blobs(orphans, settings.blobs_root, settings.blobs_quarantine_root)
        print(f"Quarantined: {moved}")

    if args.purge:
        deleted = purge_quarantine(settings.blobs_quarantine_root, args.min_age_days)
        print(f"Purged: {deleted}")
