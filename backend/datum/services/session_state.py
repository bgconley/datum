from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from datum.config import settings
from datum.models.core import Project
from datum.models.lifecycle import AgentSession


@dataclass(slots=True)
class SessionStateSnapshot:
    session_id: str
    status: str
    is_dirty: bool
    dirty_reasons: dict[str, int]


async def get_session_by_session_id(
    session_id: str,
    db: AsyncSession,
) -> AgentSession | None:
    result = await db.execute(
        select(AgentSession).where(AgentSession.session_id == session_id)
    )
    return result.scalar_one_or_none()


async def get_session(session_uuid: str, db: AsyncSession) -> AgentSession | None:
    return await db.get(AgentSession, session_uuid)


async def start_session(
    *,
    session_id: str,
    project_slug: str | None,
    client_type: str,
    db: AsyncSession,
    enforcement_mode: str | None = None,
) -> AgentSession:
    existing = await get_session_by_session_id(session_id, db)
    if existing is not None:
        if project_slug and existing.project_id is None:
            project_result = await db.execute(
                select(Project).where(Project.slug == project_slug)
            )
            project = project_result.scalar_one_or_none()
            if project is not None:
                existing.project_id = project.id
                await db.commit()
                await db.refresh(existing)
        return existing

    project_id = None
    if project_slug:
        project_result = await db.execute(
            select(Project).where(Project.slug == project_slug)
        )
        project = project_result.scalar_one_or_none()
        if project is not None:
            project_id = project.id

    row = AgentSession(
        session_id=session_id,
        project_id=project_id,
        client_type=client_type,
        status="active",
        enforcement_mode=enforcement_mode or settings.lifecycle_enforcement_mode,
        is_dirty=False,
        dirty_reasons={},
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def mark_dirty(session_id: str, reason: str, db: AsyncSession) -> AgentSession | None:
    row = await get_session_by_session_id(session_id, db)
    if row is None:
        return None
    reasons = dict(row.dirty_reasons or {})
    reasons[reason] = reasons.get(reason, 0) + 1
    row.is_dirty = True
    row.dirty_reasons = reasons
    await db.flush()
    return row


async def mark_clean(session_id: str, db: AsyncSession) -> AgentSession | None:
    row = await get_session_by_session_id(session_id, db)
    if row is None:
        return None
    row.is_dirty = False
    row.dirty_reasons = {}
    row.last_flush_at = datetime.now(UTC)
    await db.flush()
    return row


async def finalize_session(session_id: str, db: AsyncSession) -> AgentSession:
    row = await get_session_by_session_id(session_id, db)
    if row is None:
        raise ValueError(f"Session '{session_id}' not found")
    if row.status == "finalized":
        return row
    row.status = "finalized"
    row.ended_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(row)
    return row


async def abandon_stale_sessions(max_age_hours: int, db: AsyncSession) -> int:
    cutoff = datetime.now(UTC) - timedelta(hours=max_age_hours)
    result = await db.execute(
        select(AgentSession).where(
            AgentSession.status == "active",
            AgentSession.started_at < cutoff,
        )
    )
    rows = list(result.scalars().all())
    for row in rows:
        row.status = "abandoned"
        row.ended_at = datetime.now(UTC)
    if rows:
        await db.commit()
    return len(rows)
