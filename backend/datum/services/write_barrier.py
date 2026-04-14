from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from datum.config import settings
from datum.db import get_session
from datum.services.preflight import check_preflight


@dataclass(slots=True)
class WriteBarrierConfig:
    enforcement_mode: str = "advisory"
    preflight_ttl: int = 300


@dataclass(slots=True)
class WriteBarrierResult:
    blocked: bool
    detail: dict
    advisory: str | None = None


async def evaluate_write_barrier(
    *,
    session_id: str | None,
    db: AsyncSession,
    config: WriteBarrierConfig,
) -> WriteBarrierResult:
    if session_id is None:
        detail = {
            "error": "preflight_required",
            "reason": "missing_session",
            "needed_actions": ["start_session", "get_project_context"],
        }
        if config.enforcement_mode == "blocking":
            return WriteBarrierResult(blocked=True, detail=detail)
        return WriteBarrierResult(
            blocked=False,
            detail=detail,
            advisory="No session provided; lifecycle barrier running in advisory mode.",
        )

    preflight = await check_preflight(
        session_id,
        db,
        ttl_seconds=config.preflight_ttl,
    )
    if preflight.allowed:
        return WriteBarrierResult(blocked=False, detail={})

    detail = {
        "error": "preflight_required",
        "reason": preflight.reason,
        "needed_actions": preflight.needed_actions,
        "session_id": session_id,
    }
    if config.enforcement_mode == "blocking":
        return WriteBarrierResult(blocked=True, detail=detail)
    return WriteBarrierResult(
        blocked=False,
        detail=detail,
        advisory=(
            "Preflight required but advisory mode is enabled. "
            f"Run {', '.join(preflight.needed_actions)} first."
        ),
    )


async def require_preflight(
    x_session_id: Annotated[str | None, Header(alias="X-Session-ID")] = None,
    db: AsyncSession = Depends(get_session),
) -> WriteBarrierResult | None:
    if not settings.lifecycle_enabled:
        return None
    result = await evaluate_write_barrier(
        session_id=x_session_id,
        db=db,
        config=WriteBarrierConfig(
            enforcement_mode=settings.lifecycle_enforcement_mode,
            preflight_ttl=settings.preflight_ttl_seconds,
        ),
    )
    if result.blocked:
        raise HTTPException(status_code=428, detail=result.detail)
    return result
