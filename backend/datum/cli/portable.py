"""Portable import/export CLI."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from datum.services.portable_bundle import export_project_bundle, import_project_bundle


def build_parser(*, prog: str = "datum portable") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog)
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser("export", help="Export a portable project bundle")
    export_parser.add_argument("project_slug")
    export_parser.add_argument("--output", type=Path)
    export_parser.add_argument("--include-operational", action="store_true")

    import_parser = subparsers.add_parser("import", help="Import a portable project bundle")
    import_parser.add_argument("bundle_path", type=Path)
    import_parser.add_argument(
        "--conflict",
        choices=("skip", "merge", "replace"),
        default="merge",
    )

    return parser


def main(argv: Sequence[str] | None = None, *, prog: str = "datum portable") -> None:
    parser = build_parser(prog=prog)
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.command == "export":
        export_result = export_project_bundle(
            args.project_slug,
            output_path=args.output,
            include_operational=args.include_operational,
        )
        print(export_result.bundle_path)
        return

    if args.command == "import":
        import_result = import_project_bundle(
            args.bundle_path,
            conflict_strategy=args.conflict,
        )
        print(import_result.project_path)
        return
