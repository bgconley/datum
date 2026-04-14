#!/usr/bin/env python3
"""Bootstrap the first admin API key directly against the database."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from datum.db import async_session_factory, engine  # noqa: E402
from datum.services.api_keys import generate_api_key  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--name",
        default="bootstrap-admin",
        help="Human-readable name for the created admin key.",
    )
    parser.add_argument(
        "--created-by",
        default="bootstrap-script",
        help="Created-by marker stored with the key.",
    )
    return parser.parse_args()


async def _main() -> None:
    args = _parse_args()
    async with async_session_factory() as session:
        created = await generate_api_key(
            session,
            name=args.name,
            scope="admin",
            created_by=args.created_by,
        )
        await session.commit()
        print("Admin API key created successfully")
        print(f"Key: {created.key_plaintext}")
        print(f"ID: {created.key_id}")
        print(f"Scope: {created.scope}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
