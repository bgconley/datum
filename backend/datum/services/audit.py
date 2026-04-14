"""Enhanced audit logging and query helpers for agent operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from datum.models.core import AuditEvent


@dataclass(slots=True)
class AuditFilter:
    project_id: UUID | None = None
    actor_type: str | None = None
    actor_name: str | None = None
    operation: str | None = None
    since: datetime | None = None
    until: datetime | None = None
    limit: int = 50
    offset: int = 0


async def log_agent_audit(
    session: AsyncSession,
    *,
    actor_type: str,
    operation: str,
    project_id: UUID | None = None,
    target_path: str | None = None,
    old_hash: str | None = None,
    new_hash: str | None = None,
    actor_name: str | None = None,
    request_id: str | None = None,
    metadata: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(
        actor_type=actor_type,
        actor_name=actor_name,
        operation=operation,
        project_id=project_id,
        target_path=target_path,
        old_hash=old_hash,
        new_hash=new_hash,
        request_id=request_id,
        metadata_=metadata,
    )
    session.add(event)
    await session.flush()
    return event


async def query_audit_events(
    session: AsyncSession,
    audit_filter: AuditFilter,
) -> list[AuditEvent]:
    query = select(AuditEvent).order_by(AuditEvent.created_at.desc())
    if audit_filter.project_id is not None:
        query = query.where(AuditEvent.project_id == audit_filter.project_id)
    if audit_filter.actor_type is not None:
        query = query.where(AuditEvent.actor_type == audit_filter.actor_type)
    if audit_filter.actor_name is not None:
        query = query.where(AuditEvent.actor_name == audit_filter.actor_name)
    if audit_filter.operation is not None:
        query = query.where(AuditEvent.operation == audit_filter.operation)
    if audit_filter.since is not None:
        query = query.where(AuditEvent.created_at >= audit_filter.since)
    if audit_filter.until is not None:
        query = query.where(AuditEvent.created_at <= audit_filter.until)
    query = query.offset(audit_filter.offset).limit(audit_filter.limit)
    result = await session.execute(query)
    return list(result.scalars().all())
