"""Datum root CLI entrypoint."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from datum.cli import doctor as doctor_cli
from datum.cli import eval as eval_cli
from datum.cli import gc as gc_cli
from datum.cli import insights as insights_cli


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="datum", description="Datum command-line interface")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("eval", help="Evaluation harness and re-embedding workflows")
    subparsers.add_parser("insights", help="Insight analysis and listing")
    subparsers.add_parser("doctor", help="Run cabinet and DB integrity checks")
    subparsers.add_parser("gc", help="Blob garbage collection")
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
    if args:
        parser.error(f"unknown command: {args[0]}")
        return
