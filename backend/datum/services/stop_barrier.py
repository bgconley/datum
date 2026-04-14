from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from datum.services.delta_aggregator import build_flush_summary, get_unflushed_deltas
from datum.services.session_state import get_session_by_session_id


@dataclass(slots=True)
class StopBarrierResult:
    blocked: bool
    detail: dict
    advisory: str | None = None


async def evaluate_stop_barrier(
    session_id: str | None,
    db: AsyncSession,
    *,
    enforcement_mode: str,
) -> StopBarrierResult:
    if session_id is None:
        return StopBarrierResult(blocked=False, detail={})

    row = await get_session_by_session_id(session_id, db)
    if row is None:
        return StopBarrierResult(blocked=False, detail={})

    deltas = await get_unflushed_deltas(session_id, db)
    if not row.is_dirty and not deltas:
        return StopBarrierResult(blocked=False, detail={})

    summary = build_flush_summary(deltas)
    detail = {
        "error": "dirty_session",
        "session_id": session_id,
        "dirty_reasons": row.dirty_reasons or summary.counts,
        "unflushed_delta_count": len(deltas),
        "needed_actions": ["flush_deltas", "append_session_notes"],
        "summary": {
            "counts": summary.counts,
            "recent_paths": summary.recent_paths,
            "recent_commands": summary.recent_commands,
        },
    }
    if enforcement_mode == "blocking":
        return StopBarrierResult(blocked=True, detail=detail)
    return StopBarrierResult(
        blocked=False,
        detail=detail,
        advisory=(
            "Session has unflushed activity. "
            "Call flush_deltas or append_session_notes before stopping."
        ),
    )
