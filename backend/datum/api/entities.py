"""Entity list and detail API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from datum.db import get_session
from datum.schemas.entity import (
    EntityDetailResponse,
    EntityListResponse,
    EntityMentionDetailResponse,
    EntityRelationshipDetailResponse,
    EntitySummaryResponse,
)
from datum.services.entities import get_project_entity_detail, list_project_entities

router = APIRouter(prefix="/api/v1/projects/{slug}/entities", tags=["entities"])


@router.get("", response_model=EntityListResponse)
async def api_list_entities(
    slug: str,
    entity_type: str | None = None,
    limit: int = 100,
    session: AsyncSession = Depends(get_session),
):
    try:
        entities = await list_project_entities(
            session,
            slug,
            entity_type=entity_type,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return EntityListResponse(
        entities=[
            EntitySummaryResponse.model_validate(entity, from_attributes=True)
            for entity in entities
        ],
        total=len(entities),
    )


@router.get("/{entity_id}", response_model=EntityDetailResponse)
async def api_get_entity_detail(
    slug: str,
    entity_id: str,
    session: AsyncSession = Depends(get_session),
):
    try:
        detail = await get_project_entity_detail(session, slug, entity_id=entity_id)
    except ValueError as exc:
        detail_text = str(exc)
        status_code = 404 if "not found" in detail_text.lower() else 422
        raise HTTPException(status_code=status_code, detail=detail_text) from exc

    return EntityDetailResponse(
        id=detail.id,
        entity_type=detail.entity_type,
        canonical_name=detail.canonical_name,
        mentions=[
            EntityMentionDetailResponse.model_validate(item, from_attributes=True)
            for item in detail.mentions
        ],
        relationships=[
            EntityRelationshipDetailResponse.model_validate(item, from_attributes=True)
            for item in detail.relationships
        ],
        mention_count=detail.mention_count,
    )
