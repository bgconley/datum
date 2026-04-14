"""Datum insight analysis CLI."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections.abc import Sequence

from datum.db import async_session_factory
from datum.services.insight_analysis import run_insight_analysis
from datum.services.intelligence import get_project_or_404
from datum.services.traceability import list_project_insights

logger = logging.getLogger(__name__)


async def cmd_analyze(args: argparse.Namespace) -> None:
    async with async_session_factory() as session:
        project = await get_project_or_404(session, args.project_slug)
        result = await run_insight_analysis(
            session,
            project.id,
            max_age_days=args.max_age_days,
        )
        await session.commit()

    print(f"Insight analysis complete for {args.project_slug}")
    print(f"  Contradictions found: {result.contradictions_found}")
    print(f"  Staleness issues found: {result.staleness_found}")
    print(f"  Insights created: {result.insights_created}")
    print(f"  Insights skipped: {result.insights_skipped}")


async def cmd_list(args: argparse.Namespace) -> None:
    async with async_session_factory() as session:
        insights = await list_project_insights(
            session,
            args.project_slug,
            status=args.status,
        )

    if not insights:
        print(f"No insights found for {args.project_slug}.")
        return

    print(f"Insights for {args.project_slug} ({len(insights)} total):")
    for insight in insights:
        confidence = f"{insight.confidence:.2f}" if insight.confidence is not None else "-"
        print(
            f"- [{insight.severity}] {insight.title} "
            f"(type={insight.insight_type}, status={insight.status}, confidence={confidence})"
        )


def build_parser(prog: str = "datum-insights") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog, description="Datum insight analysis")
    subparsers = parser.add_subparsers(dest="command")

    analyze = subparsers.add_parser(
        "analyze",
        help="Analyze a project for contradictions and staleness",
    )
    analyze.add_argument("project_slug")
    analyze.add_argument("--max-age-days", type=int, default=60)

    list_parser = subparsers.add_parser("list", help="List insights for a project")
    list_parser.add_argument("project_slug")
    list_parser.add_argument("--status", default=None)

    return parser


async def _dispatch(args: argparse.Namespace) -> None:
    commands = {
        "analyze": cmd_analyze,
        "list": cmd_list,
    }
    handler = commands.get(args.command)
    if handler is None:
        raise SystemExit(2)
    await handler(args)


def main(argv: Sequence[str] | None = None, *, prog: str = "datum-insights") -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = build_parser(prog=prog)
    args = parser.parse_args(list(argv) if argv is not None else None)
    if not args.command:
        parser.print_help()
        return

    try:
        asyncio.run(_dispatch(args))
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
