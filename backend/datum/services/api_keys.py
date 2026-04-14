"""API key generation, validation, and lifecycle management."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from datum.models.agent import ApiKey

SCOPE_HIERARCHY = {
    "read": 1,
    "readwrite": 2,
    "admin": 3,
}

_SCOPE_PREFIX = {
    "read": "datum_ro_",
    "readwrite": "datum_rw_",
    "admin": "datum_adm_",
}


@dataclass(slots=True)
class GeneratedApiKey:
    key_plaintext: str
    key_id: str
    name: str
    scope: str
    prefix: str


class ScopedKey(Protocol):
    scope: str


def _hash_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def has_scope(key: ApiKey | ScopedKey | str, required_scope: str) -> bool:
    actual_scope = key if isinstance(key, str) else key.scope
    return SCOPE_HIERARCHY.get(actual_scope, 0) >= SCOPE_HIERARCHY.get(required_scope, 0)


async def generate_api_key(
    session: AsyncSession,
    name: str,
    scope: str,
    *,
    expires_days: int | None = None,
    created_by: str | None = None,
) -> GeneratedApiKey:
    if scope not in SCOPE_HIERARCHY:
        raise ValueError(f"Invalid scope: {scope}")

    plaintext = _SCOPE_PREFIX[scope] + secrets.token_urlsafe(24)
    key = ApiKey(
        key_hash=_hash_key(plaintext),
        key_prefix=plaintext[:12],
        name=name,
        scope=scope,
        created_by=created_by,
        expires_at=(
            datetime.now(UTC) + timedelta(days=expires_days) if expires_days is not None else None
        ),
    )
    session.add(key)
    await session.flush()
    return GeneratedApiKey(
        key_plaintext=plaintext,
        key_id=str(key.id),
        name=key.name,
        scope=key.scope,
        prefix=key.key_prefix,
    )


async def validate_api_key(session: AsyncSession, plaintext: str) -> ApiKey | None:
    result = await session.execute(select(ApiKey).where(ApiKey.key_hash == _hash_key(plaintext)))
    key = result.scalar_one_or_none()
    if key is None or not key.is_active:
        return None
    if key.expires_at is not None and key.expires_at <= datetime.now(UTC):
        return None
    key.last_used_at = datetime.now(UTC)
    await session.flush()
    return key


async def revoke_api_key(session: AsyncSession, key_id: str) -> bool:
    key = await session.get(ApiKey, key_id)
    if key is None:
        return False
    key.is_active = False
    await session.flush()
    return True


async def list_api_keys(session: AsyncSession) -> list[ApiKey]:
    result = await session.execute(select(ApiKey).order_by(ApiKey.created_at.desc()))
    return list(result.scalars().all())
