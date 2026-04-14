from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from datum.services.session_state import get_session_by_session_id

QUALIFYING_PREFLIGHT_ACTIONS = (
    "get_project_context",
    "search_project_memory",
    "list_candidates",
)


@dataclass(slots=True)
class PreflightResult:
    allowed: bool
    reason: str = ""
    needed_actions: list[str] = field(default_factory=list)


async def record_preflight(
    session_id: str,
    action: str,
    db: AsyncSession,
) -> bool:
    if action not in QUALIFYING_PREFLIGHT_ACTIONS:
        raise ValueError(f"Unsupported preflight action: {action}")
    row = await get_session_by_session_id(session_id, db)
    if row is None:
        return False
    row.last_preflight_at = datetime.now(UTC)
    row.last_preflight_action = action
    await db.flush()
    return True


async def check_preflight(
    session_id: str,
    db: AsyncSession,
    *,
    ttl_seconds: int,
) -> PreflightResult:
    row = await get_session_by_session_id(session_id, db)
    if row is None:
        return PreflightResult(
            allowed=False,
            reason="missing_session",
            needed_actions=["start_session", *QUALIFYING_PREFLIGHT_ACTIONS],
        )

    if row.last_preflight_at is None:
        return PreflightResult(
            allowed=False,
            reason="no_preflight",
            needed_actions=list(QUALIFYING_PREFLIGHT_ACTIONS),
        )

    age_seconds = (datetime.now(UTC) - row.last_preflight_at).total_seconds()
    if age_seconds > ttl_seconds:
        return PreflightResult(
            allowed=False,
            reason="preflight_expired",
            needed_actions=list(QUALIFYING_PREFLIGHT_ACTIONS),
        )

    return PreflightResult(allowed=True)
