"""CLI entrypoint for the full datum doctor suite."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Sequence
from pathlib import Path
from typing import TypedDict, cast

from sqlalchemy import select

from datum.config import settings
from datum.db import async_session_factory
from datum.models.core import Project
from datum.services.doctor import check_project, full_check
from datum.services.project_manager import get_project


class DoctorPayload(TypedDict):
    errors: list[str]
    warnings: list[str]
    is_healthy: bool
    files_checked: int
    versions_checked: int


async def _run_full_check(slug: str) -> DoctorPayload:
    async with async_session_factory() as session:
        result = await session.execute(select(Project).where(Project.slug == slug))
        project = result.scalar_one_or_none()
        if project is None:
            raise SystemExit(f"Project '{slug}' not found in DB")
        return cast(
            DoctorPayload,
            await full_check(
                session,
                project_id=project.id,
                project_root=settings.projects_root / slug,
                blobs_root=settings.blobs_root,
            ),
        )


def main(argv: Sequence[str] | None = None, *, prog: str = "datum doctor") -> None:
    parser = argparse.ArgumentParser(prog=prog, description="Datum integrity checker")
    parser.add_argument("project", help="project slug or absolute project path")
    parser.add_argument("--basic", action="store_true", help="run filesystem-only checks")
    parser.add_argument("--json", action="store_true", help="emit JSON output")
    args = parser.parse_args(list(argv) if argv is not None else None)

    maybe_path = Path(args.project)
    if maybe_path.is_absolute():
        report = check_project(maybe_path)
        payload: DoctorPayload = {
            "errors": report.errors,
            "warnings": report.warnings,
            "is_healthy": report.is_healthy,
            "files_checked": report.files_checked,
            "versions_checked": report.versions_checked,
        }
    elif args.basic:
        project = get_project(settings.projects_root, args.project)
        if project is None:
            raise SystemExit(f"Project '{args.project}' not found")
        report = check_project(settings.projects_root / args.project)
        payload = {
            "errors": report.errors,
            "warnings": report.warnings,
            "is_healthy": report.is_healthy,
            "files_checked": report.files_checked,
            "versions_checked": report.versions_checked,
        }
    else:
        payload = asyncio.run(_run_full_check(args.project))

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return

    print(f"healthy={payload['is_healthy']}")
    print(f"errors={len(payload['errors'])} warnings={len(payload['warnings'])}")
    for message in payload["errors"]:
        print(f"ERROR: {message}")
    for message in payload["warnings"]:
        print(f"WARNING: {message}")
