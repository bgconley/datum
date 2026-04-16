"""Dashboard API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from datum.config import get_settings, Settings
from datum.db import get_session
from datum.models.core import Project
from datum.schemas.dashboard import (
    ActivityEvent,
    AgentActivityStats,
    HealthResponse,
    IngestionStats,
    SessionDetail,
    SessionSummary,
)
from datum.services.dashboard import (
    get_activity_feed,
    get_agent_activity,
    get_ingestion_stats,
    get_session_detail,
    get_sessions_list,
    get_system_health,
)

router = APIRouter(prefix="/api/v1", tags=["dashboard"])


async def _resolve_project_id(slug: str, db: AsyncSession):
    """Look up project by slug, raise 404 if not found."""
    result = await db.execute(select(Project).where(Project.slug == slug))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")
    return project.id


@router.get("/dashboard/health", response_model=HealthResponse)
async def api_system_health(
    db: AsyncSession = Depends(get_session),
    app_settings: Settings = Depends(get_settings),
):
    return await get_system_health(db, app_settings)


@router.get(
    "/projects/{slug}/dashboard/ingestion",
    response_model=IngestionStats,
)
async def api_ingestion_stats(
    slug: str,
    db: AsyncSession = Depends(get_session),
):
    project_id = await _resolve_project_id(slug, db)
    return await get_ingestion_stats(db, project_id)


@router.get(
    "/projects/{slug}/dashboard/agent-activity",
    response_model=AgentActivityStats,
)
async def api_agent_activity(
    slug: str,
    hours: int = Query(default=24, ge=1, le=720),
    db: AsyncSession = Depends(get_session),
):
    project_id = await _resolve_project_id(slug, db)
    return await get_agent_activity(db, project_id, hours=hours)


@router.get(
    "/projects/{slug}/dashboard/activity",
    response_model=list[ActivityEvent],
)
async def api_activity_feed(
    slug: str,
    limit: int = Query(default=20, ge=1, le=200),
    db: AsyncSession = Depends(get_session),
):
    project_id = await _resolve_project_id(slug, db)
    return await get_activity_feed(db, project_id, limit=limit)


@router.get(
    "/projects/{slug}/dashboard/sessions",
    response_model=list[SessionSummary],
)
async def api_sessions_list(
    slug: str,
    hours: int = Query(default=24, ge=1, le=720),
    limit: int = Query(default=50, ge=1, le=500),
    db: AsyncSession = Depends(get_session),
):
    project_id = await _resolve_project_id(slug, db)
    return await get_sessions_list(db, project_id, hours=hours, limit=limit)


@router.get(
    "/projects/{slug}/dashboard/sessions/{session_id}",
    response_model=SessionDetail,
)
async def api_session_detail(
    slug: str,
    session_id: str,
    db: AsyncSession = Depends(get_session),
):
    # Verify project exists
    await _resolve_project_id(slug, db)
    detail = await get_session_detail(db, session_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return detail
