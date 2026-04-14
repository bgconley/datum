from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from datum.config import settings
from datum.db import get_session
from datum.schemas.lifecycle import (
    DeltaRequest,
    DeltaResponse,
    FinalizeResponse,
    FlushResponse,
    FlushSummaryResponse,
    PreflightRequest,
    PreflightResponse,
    SessionStartRequest,
    SessionStartResponse,
    SessionStatusResponse,
)
from datum.services.delta_aggregator import flush_deltas, get_unflushed_deltas, record_delta
from datum.services.preflight import record_preflight
from datum.services.session_state import finalize_session, get_session_by_session_id, start_session
from datum.services.stop_barrier import evaluate_stop_barrier

router = APIRouter(prefix="/api/v1/agent/sessions", tags=["lifecycle"])


@router.post("/start", response_model=SessionStartResponse, status_code=201)
async def start_agent_session(
    req: SessionStartRequest,
    db: AsyncSession = Depends(get_session),
):
    row = await start_session(
        session_id=req.session_id,
        project_slug=req.project_slug,
        client_type=req.client_type,
        db=db,
    )
    return SessionStartResponse(
        id=str(row.id),
        session_id=row.session_id,
        project_id=str(row.project_id) if row.project_id else None,
        client_type=row.client_type,
        status=row.status,
        enforcement_mode=row.enforcement_mode,
        is_dirty=row.is_dirty,
        started_at=row.started_at,
    )


@router.post("/{session_id}/preflight", response_model=PreflightResponse)
async def record_agent_preflight(
    session_id: str,
    req: PreflightRequest,
    db: AsyncSession = Depends(get_session),
):
    recorded = await record_preflight(session_id, req.action, db)
    if not recorded:
        raise HTTPException(status_code=404, detail="Session not found")
    await db.commit()
    return PreflightResponse(recorded=True, action=req.action, session_id=session_id)


@router.post("/{session_id}/delta", response_model=DeltaResponse, status_code=201)
async def record_agent_delta(
    session_id: str,
    req: DeltaRequest,
    db: AsyncSession = Depends(get_session),
):
    try:
        row = await record_delta(
            session_id,
            req.delta_type,
            req.detail,
            db,
            summary_text=req.summary_text,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await db.commit()
    return DeltaResponse(
        id=str(row.id),
        delta_type=row.delta_type,
        detail=row.detail,
        flushed=row.flushed,
        created_at=row.created_at,
    )


@router.get("/{session_id}/status", response_model=SessionStatusResponse)
async def get_agent_session_status(
    session_id: str,
    db: AsyncSession = Depends(get_session),
):
    row = await get_session_by_session_id(session_id, db)
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    deltas = await get_unflushed_deltas(session_id, db)
    return SessionStatusResponse(
        session_id=row.session_id,
        status=row.status,
        enforcement_mode=row.enforcement_mode,
        is_dirty=row.is_dirty,
        dirty_reasons=row.dirty_reasons,
        last_preflight_at=row.last_preflight_at,
        last_preflight_action=row.last_preflight_action,
        last_flush_at=row.last_flush_at,
        started_at=row.started_at,
        ended_at=row.ended_at,
        unflushed_delta_count=len(deltas),
    )


@router.post("/{session_id}/flush", response_model=FlushResponse)
async def flush_agent_deltas(
    session_id: str,
    db: AsyncSession = Depends(get_session),
):
    row = await get_session_by_session_id(session_id, db)
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    result = await flush_deltas(session_id, db, write_session_note=True)
    return FlushResponse(
        flushed_count=result.flushed_count,
        session_id=session_id,
        summary=(
            FlushSummaryResponse(
                counts=result.summary.counts,
                recent_paths=result.summary.recent_paths,
                recent_commands=result.summary.recent_commands,
            )
            if result.summary
            else None
        ),
        session_note_path=result.session_note_path,
    )


@router.post("/{session_id}/finalize", response_model=FinalizeResponse)
async def finalize_agent_session(
    session_id: str,
    db: AsyncSession = Depends(get_session),
):
    row = await get_session_by_session_id(session_id, db)
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    barrier = await evaluate_stop_barrier(
        session_id,
        db,
        enforcement_mode=settings.lifecycle_enforcement_mode,
    )
    if barrier.blocked:
        raise HTTPException(status_code=409, detail=barrier.detail)
    finalized = await finalize_session(session_id, db)
    return FinalizeResponse(
        session_id=finalized.session_id,
        status=finalized.status,
        ended_at=finalized.ended_at,
    )
