"""Service layer for dashboard endpoints."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from datum.config import Settings
from datum.models.core import AuditEvent, Project
from datum.models.lifecycle import AgentSession, HookEvent, SessionDelta
from datum.models.search import IngestionJob
from datum.schemas.dashboard import (
    ActivityEvent,
    AgentActivityStats,
    HealthResponse,
    HealthStatus,
    HookEventResponse,
    IngestionStats,
    SessionDetail,
    SessionSummary,
)
from datum.services.model_gateway import build_model_gateway

logger = logging.getLogger(__name__)

_HEALTH_TIMEOUT = 3.0


async def _check_db_health(db: AsyncSession) -> HealthStatus:
    """Check database connectivity with SELECT 1."""
    start = time.monotonic()
    try:
        await db.execute(select(func.literal(1)))
        latency = (time.monotonic() - start) * 1000
        return HealthStatus(name="paradedb", healthy=True, latency_ms=latency)
    except Exception as exc:
        latency = (time.monotonic() - start) * 1000
        return HealthStatus(
            name="paradedb", healthy=False, latency_ms=latency, error=str(exc)
        )


async def _check_watcher_health(heartbeat_path: Path) -> HealthStatus:
    """Check watcher heartbeat file freshness (stale if >60s old)."""
    start = time.monotonic()
    try:
        if not heartbeat_path.exists():
            latency = (time.monotonic() - start) * 1000
            return HealthStatus(
                name="file_watcher",
                healthy=False,
                latency_ms=latency,
                error="heartbeat file not found",
            )
        stat = heartbeat_path.stat()
        age = time.time() - stat.st_mtime
        latency = (time.monotonic() - start) * 1000
        if age > 60:
            return HealthStatus(
                name="file_watcher",
                healthy=False,
                latency_ms=latency,
                error=f"heartbeat stale ({age:.0f}s old)",
            )
        return HealthStatus(name="file_watcher", healthy=True, latency_ms=latency)
    except Exception as exc:
        latency = (time.monotonic() - start) * 1000
        return HealthStatus(
            name="file_watcher", healthy=False, latency_ms=latency, error=str(exc)
        )


async def _check_zfs_mount(projects_root: Path) -> HealthStatus:
    """Check ZFS by verifying the projects root mount is accessible."""
    start = time.monotonic()
    try:
        exists = projects_root.exists() and projects_root.is_dir()
        latency = (time.monotonic() - start) * 1000
        if exists:
            return HealthStatus(name="zfs_pool", healthy=True, latency_ms=latency)
        return HealthStatus(
            name="zfs_pool", healthy=False, latency_ms=latency, error="mount not accessible"
        )
    except Exception as exc:
        latency = (time.monotonic() - start) * 1000
        return HealthStatus(
            name="zfs_pool", healthy=False, latency_ms=latency, error=str(exc)
        )


async def _check_worker_queue_health(db: AsyncSession) -> HealthStatus:
    """Check worker queue by counting active ingestion jobs."""
    start = time.monotonic()
    try:
        result = await db.execute(
            select(func.count()).select_from(IngestionJob).where(
                IngestionJob.status.in_(["queued", "processing"])
            )
        )
        active_jobs = result.scalar() or 0
        latency = (time.monotonic() - start) * 1000
        return HealthStatus(
            name="worker_queue",
            healthy=True,
            latency_ms=latency,
            error=f"{active_jobs} jobs" if active_jobs > 0 else None,
        )
    except Exception as exc:
        latency = (time.monotonic() - start) * 1000
        return HealthStatus(
            name="worker_queue", healthy=False, latency_ms=latency, error=str(exc)
        )


async def _check_model_health(model_type: str, display_name: str) -> HealthStatus:
    """Check a model service health endpoint with latency timing."""
    gateway = build_model_gateway()
    start = time.monotonic()
    try:
        healthy = await gateway.check_health(model_type)
        latency = (time.monotonic() - start) * 1000
        return HealthStatus(name=display_name, healthy=healthy, latency_ms=latency)
    except Exception as exc:
        latency = (time.monotonic() - start) * 1000
        return HealthStatus(
            name=display_name, healthy=False, latency_ms=latency, error=str(exc)
        )
    finally:
        await gateway.close()


async def _check_zfs_health(zfs_status_path: Path) -> HealthStatus:
    """Check ZFS status file if configured."""
    start = time.monotonic()
    try:
        if not zfs_status_path.exists():
            latency = (time.monotonic() - start) * 1000
            return HealthStatus(
                name="zfs_pool", healthy=False, latency_ms=latency, error="status file not found"
            )
        content = zfs_status_path.read_text().strip().lower()
        latency = (time.monotonic() - start) * 1000
        healthy = content in {"online", "healthy", "ok"}
        return HealthStatus(
            name="zfs_pool",
            healthy=healthy,
            latency_ms=latency,
            error=None if healthy else f"status: {content}",
        )
    except Exception as exc:
        latency = (time.monotonic() - start) * 1000
        return HealthStatus(
            name="zfs_pool", healthy=False, latency_ms=latency, error=str(exc)
        )


async def get_system_health(db: AsyncSession, app_settings: Settings) -> HealthResponse:
    """Composite system health check. Always returns result, never raises."""
    try:
        tasks: list[asyncio.Task] = []

        async def _gather_with_timeout():
            coros = [
                _check_db_health(db),
                _check_watcher_health(app_settings.watcher_heartbeat_path),
                _check_worker_queue_health(db),
                _check_model_health("embedding", "embedder"),
                _check_model_health("reranker", "reranker"),
                _check_model_health("ner", "gliner_ner"),
                _check_model_health("llm", "llm"),
            ]
            # Always check ZFS — use status file if available, otherwise check projects_root mount
            if app_settings.zfs_status_path is not None:
                coros.append(_check_zfs_health(app_settings.zfs_status_path))
            else:
                coros.append(_check_zfs_mount(app_settings.projects_root))

            results = await asyncio.gather(*coros, return_exceptions=True)
            subsystems: list[HealthStatus] = []
            for result in results:
                if isinstance(result, Exception):
                    subsystems.append(
                        HealthStatus(name="unknown", healthy=False, error=str(result))
                    )
                else:
                    subsystems.append(result)
            return subsystems

        try:
            subsystems = await asyncio.wait_for(
                _gather_with_timeout(), timeout=_HEALTH_TIMEOUT
            )
        except asyncio.TimeoutError:
            subsystems = [
                HealthStatus(name="timeout", healthy=False, error="health check timed out")
            ]

        overall = all(s.healthy for s in subsystems)
        return HealthResponse(
            subsystems=subsystems,
            healthy=overall,
            checked_at=datetime.now(UTC),
        )
    except Exception as exc:
        logger.exception("Health check failed unexpectedly")
        return HealthResponse(
            subsystems=[
                HealthStatus(name="system", healthy=False, error=str(exc))
            ],
            healthy=False,
            checked_at=datetime.now(UTC),
        )


async def get_ingestion_stats(db: AsyncSession, project_id: UUID) -> IngestionStats:
    """Aggregate IngestionJob counts by status for a project."""
    result = await db.execute(
        select(
            IngestionJob.status,
            func.count(IngestionJob.id),
        )
        .where(IngestionJob.project_id == project_id)
        .group_by(IngestionJob.status)
    )

    counts: dict[str, int] = {}
    for status, count in result.fetchall():
        counts[status] = count

    return IngestionStats(
        queued=counts.get("queued", 0),
        processing=counts.get("processing", 0),
        completed=counts.get("completed", 0),
        failed=counts.get("failed", 0),
        total=sum(counts.values()),
    )


async def get_agent_activity(
    db: AsyncSession, project_id: UUID, hours: int = 24
) -> AgentActivityStats:
    """Count sessions, group hook events, and count MCP operations."""
    cutoff = datetime.now(UTC) - timedelta(hours=hours)

    # Session counts
    session_result = await db.execute(
        select(
            func.count(AgentSession.id),
            func.count(
                case(
                    (AgentSession.status == "active", AgentSession.id),
                )
            ),
        )
        .where(
            AgentSession.project_id == project_id,
            AgentSession.started_at >= cutoff,
        )
    )
    row = session_result.fetchone()
    sessions_total = row[0] if row else 0
    sessions_active = row[1] if row else 0

    # Hook event counts by type
    hook_result = await db.execute(
        select(HookEvent.hook_type, func.count(HookEvent.id))
        .join(AgentSession, HookEvent.agent_session_id == AgentSession.id)
        .where(
            AgentSession.project_id == project_id,
            HookEvent.created_at >= cutoff,
        )
        .group_by(HookEvent.hook_type)
    )
    hook_event_counts: dict[str, int] = {}
    for hook_type, count in hook_result.fetchall():
        hook_event_counts[hook_type] = count

    # MCP operation counts from audit events
    mcp_result = await db.execute(
        select(AuditEvent.operation, func.count(AuditEvent.id))
        .where(
            AuditEvent.project_id == project_id,
            AuditEvent.actor_type == "mcp",
            AuditEvent.created_at >= cutoff,
        )
        .group_by(AuditEvent.operation)
    )
    mcp_op_counts: dict[str, int] = {}
    for operation, count in mcp_result.fetchall():
        mcp_op_counts[operation] = count

    return AgentActivityStats(
        sessions_active=sessions_active,
        sessions_total=sessions_total,
        hook_event_counts=hook_event_counts,
        mcp_op_counts=mcp_op_counts,
    )


async def get_activity_feed(
    db: AsyncSession, project_id: UUID, limit: int = 20
) -> list[ActivityEvent]:
    """Query recent audit events ordered by created_at DESC."""
    result = await db.execute(
        select(AuditEvent)
        .where(AuditEvent.project_id == project_id)
        .order_by(AuditEvent.created_at.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [
        ActivityEvent(
            id=row.id,
            actor_type=row.actor_type,
            operation=row.operation,
            target_path=row.target_path,
            metadata=row.metadata_ or {},
            created_at=row.created_at,
        )
        for row in rows
    ]


async def get_sessions_list(
    db: AsyncSession,
    project_id: UUID,
    hours: int = 24,
    limit: int = 50,
) -> list[SessionSummary]:
    """List sessions with delta counts via LEFT JOIN."""
    cutoff = datetime.now(UTC) - timedelta(hours=hours)

    delta_count_subq = (
        select(
            SessionDelta.agent_session_id,
            func.count(SessionDelta.id).label("delta_count"),
        )
        .group_by(SessionDelta.agent_session_id)
        .subquery()
    )

    result = await db.execute(
        select(
            AgentSession,
            func.coalesce(delta_count_subq.c.delta_count, 0).label("delta_count"),
        )
        .outerjoin(delta_count_subq, AgentSession.id == delta_count_subq.c.agent_session_id)
        .where(
            AgentSession.project_id == project_id,
            AgentSession.started_at >= cutoff,
        )
        .order_by(AgentSession.started_at.desc())
        .limit(limit)
    )

    sessions: list[SessionSummary] = []
    for row in result.fetchall():
        session = row[0]
        delta_count = row[1]
        sessions.append(
            SessionSummary(
                id=session.id,
                session_id=session.session_id,
                client_type=session.client_type,
                status=session.status,
                enforcement_mode=session.enforcement_mode,
                is_dirty=session.is_dirty,
                delta_count=delta_count,
                started_at=session.started_at,
                ended_at=session.ended_at,
            )
        )
    return sessions


async def get_session_detail(db: AsyncSession, session_id: str) -> SessionDetail | None:
    """Full session with deltas, hook events, and audit events."""
    result = await db.execute(
        select(AgentSession).where(AgentSession.session_id == session_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        return None

    # Fetch deltas
    delta_result = await db.execute(
        select(SessionDelta)
        .where(SessionDelta.agent_session_id == session.id)
        .order_by(SessionDelta.created_at.asc())
    )
    deltas = [
        {
            "id": str(d.id),
            "delta_type": d.delta_type,
            "detail": d.detail,
            "summary_text": d.summary_text,
            "flushed": d.flushed,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in delta_result.scalars().all()
    ]

    # Fetch hook events
    hook_result = await db.execute(
        select(HookEvent)
        .where(HookEvent.agent_session_id == session.id)
        .order_by(HookEvent.created_at.asc())
    )
    hook_events = [
        HookEventResponse(
            id=h.id,
            hook_type=h.hook_type,
            detail=h.detail,
            created_at=h.created_at,
        )
        for h in hook_result.scalars().all()
    ]

    # Fetch audit events for this session's project
    audit_events: list[ActivityEvent] = []
    if session.project_id:
        audit_result = await db.execute(
            select(AuditEvent)
            .where(
                AuditEvent.project_id == session.project_id,
                AuditEvent.created_at >= session.started_at,
                *([AuditEvent.created_at <= session.ended_at] if session.ended_at else []),
            )
            .order_by(AuditEvent.created_at.asc())
        )
        audit_events = [
            ActivityEvent(
                id=a.id,
                actor_type=a.actor_type,
                operation=a.operation,
                target_path=a.target_path,
                metadata=a.metadata_ or {},
                created_at=a.created_at,
            )
            for a in audit_result.scalars().all()
        ]

    return SessionDetail(
        id=session.id,
        session_id=session.session_id,
        client_type=session.client_type,
        status=session.status,
        enforcement_mode=session.enforcement_mode,
        is_dirty=session.is_dirty,
        delta_count=len(deltas),
        started_at=session.started_at,
        ended_at=session.ended_at,
        deltas=deltas,
        hook_events=hook_events,
        audit_events=audit_events,
    )
