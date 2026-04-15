"""Datum root CLI entrypoint."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from datum.cli import doctor as doctor_cli
from datum.cli import eval as eval_cli
from datum.cli import gc as gc_cli
from datum.cli import insights as insights_cli
from datum.cli import portable as portable_cli


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="datum", description="Datum command-line interface")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("eval", help="Evaluation harness and re-embedding workflows")
    subparsers.add_parser("insights", help="Insight analysis and listing")
    subparsers.add_parser("doctor", help="Run cabinet and DB integrity checks")
    subparsers.add_parser("gc", help="Blob garbage collection")
    portable_parser = subparsers.add_parser("export", help="Export a portable project bundle")
    portable_parser.add_argument("project_slug")
    portable_parser.add_argument("--output")
    portable_parser.add_argument("--include-operational", action="store_true")
    import_parser = subparsers.add_parser("import", help="Import a portable project bundle")
    import_parser.add_argument("bundle_path")
    import_parser.add_argument(
        "--conflict",
        choices=("skip", "merge", "replace"),
        default="merge",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = list(argv) if argv is not None else sys.argv[1:]
    parser = build_parser()
    if not args or args[0] in {"-h", "--help"}:
        parser.print_help()
        return
    if args[0] == "eval":
        eval_cli.main(args[1:], prog="datum eval")
        return
    if args[0] == "insights":
        insights_cli.main(args[1:], prog="datum insights")
        return
    if args[0] == "doctor":
        doctor_cli.main(args[1:], prog="datum doctor")
        return
    if args[0] == "gc":
        gc_cli.main(args[1:], prog="datum gc")
        return
    if args[0] == "export":
        portable_cli.main(["export", *args[1:]], prog="datum")
        return
    if args[0] == "import":
        portable_cli.main(["import", *args[1:]], prog="datum")
        return
    if args:
        parser.error(f"unknown command: {args[0]}")
        return
