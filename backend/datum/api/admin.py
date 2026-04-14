"""Admin API: API key lifecycle and audit queries."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from datum.db import get_session
from datum.schemas.agent import (
    ApiKeyCreateRequest,
    ApiKeyCreateResponse,
    ApiKeyListItem,
    ApiKeyListResponse,
    AuditEventResponse,
    AuditListResponse,
)
from datum.services.api_keys import generate_api_key, list_api_keys, revoke_api_key
from datum.services.audit import AuditFilter, query_audit_events
from datum.services.auth import require_scope

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.post("/api-keys", response_model=ApiKeyCreateResponse, status_code=201)
async def api_create_api_key(
    body: ApiKeyCreateRequest,
    session: AsyncSession = Depends(get_session),
    admin_key=Depends(require_scope("admin")),
):
    try:
        created = await generate_api_key(
            session,
            name=body.name,
            scope=body.scope,
            expires_days=body.expires_days,
            created_by=admin_key.name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await session.commit()
    return ApiKeyCreateResponse(
        key=created.key_plaintext,
        key_id=created.key_id,
        name=created.name,
        scope=created.scope,
        prefix=created.prefix,
    )


@router.get("/api-keys", response_model=ApiKeyListResponse)
async def api_list_api_keys(
    session: AsyncSession = Depends(get_session),
    admin_key=Depends(require_scope("admin")),
):
    del admin_key
    keys = await list_api_keys(session)
    return ApiKeyListResponse(
        keys=[
            ApiKeyListItem(
                key_id=str(key.id),
                name=key.name,
                scope=key.scope,
                prefix=key.key_prefix,
                created_at=key.created_at,
                last_used_at=key.last_used_at,
                is_active=key.is_active,
                expires_at=key.expires_at,
            )
            for key in keys
        ]
    )


@router.delete("/api-keys/{key_id}")
async def api_revoke_api_key(
    key_id: str,
    session: AsyncSession = Depends(get_session),
    admin_key=Depends(require_scope("admin")),
):
    del admin_key
    revoked = await revoke_api_key(session, key_id)
    if not revoked:
        raise HTTPException(status_code=404, detail="API key not found")
    await session.commit()
    return {"status": "revoked", "key_id": key_id}


@router.get("/audit", response_model=AuditListResponse)
async def api_query_audit(
    project_id: str | None = Query(None),
    actor_type: str | None = Query(None),
    actor_name: str | None = Query(None),
    operation: str | None = Query(None),
    since: datetime | None = Query(None),
    until: datetime | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    admin_key=Depends(require_scope("admin")),
):
    del admin_key
    events = await query_audit_events(
        session,
        AuditFilter(
            project_id=project_id,
            actor_type=actor_type,
            actor_name=actor_name,
            operation=operation,
            since=since,
            until=until,
            limit=limit,
            offset=offset,
        ),
    )
    return AuditListResponse(
        events=[
            AuditEventResponse(
                id=str(event.id),
                actor_type=event.actor_type,
                actor_name=event.actor_name,
                operation=event.operation,
                target_path=event.target_path,
                created_at=event.created_at,
                metadata=event.metadata_,
            )
            for event in events
        ],
        count=len(events),
    )
