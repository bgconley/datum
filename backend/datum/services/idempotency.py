"""Idempotency key checking and response caching."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from datum.models.agent import IdempotencyRecord


async def check_idempotency(
    session: AsyncSession, key: str, scope: str | None = None
) -> dict | None:
    result = await session.execute(
        select(IdempotencyRecord).where(IdempotencyRecord.idempotency_key == key)
    )
    record = result.scalar_one_or_none()
    if record is None:
        return None
    if record.expires_at <= datetime.now(UTC):
        return None
    if scope is not None and record.scope != scope:
        return None
    return {
        "status_code": record.status_code,
        "body": record.response_body or {},
    }


async def store_idempotency(
    session: AsyncSession,
    key: str,
    scope: str,
    status_code: int,
    response_body: dict,
    *,
    ttl_hours: int = 24,
) -> None:
    session.add(
        IdempotencyRecord(
            idempotency_key=key,
            scope=scope,
            status_code=status_code,
            response_body=response_body,
            expires_at=datetime.now(UTC) + timedelta(hours=ttl_hours),
        )
    )
    await session.flush()


async def cleanup_expired(session: AsyncSession) -> int:
    now = datetime.now(UTC)
    result = await session.execute(
        delete(IdempotencyRecord)
        .where(IdempotencyRecord.expires_at <= now)
        .returning(IdempotencyRecord.id)
    )
    deleted = result.fetchall()
    await session.flush()
    return len(deleted)
