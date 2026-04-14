"""Traceability, relationship, and insight API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from datum.db import get_session
from datum.schemas.traceability import (
    AnalyzeResponse,
    DocumentLinkResponse,
    DocumentLinksListResponse,
    EntityRelationshipResponse,
    EntityRelationshipsListResponse,
    InsightResponse,
    InsightsListResponse,
    InsightStatusUpdate,
    TraceabilityChainResponse,
    TraceabilityNodeResponse,
)
from datum.services.traceability import (
    analyze_project_insights,
    get_traceability_chains,
    list_project_entity_relationships,
    list_project_insights,
    list_project_links,
    update_project_insight_status,
)

router = APIRouter(prefix="/api/v1/projects/{slug}", tags=["traceability"])


@router.get("/links", response_model=DocumentLinksListResponse)
async def api_list_document_links(
    slug: str,
    session: AsyncSession = Depends(get_session),
):
    try:
        links = await list_project_links(session, slug)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return DocumentLinksListResponse(
        links=[DocumentLinkResponse.model_validate(link, from_attributes=True) for link in links],
        total=len(links),
    )


@router.get("/relationships", response_model=EntityRelationshipsListResponse)
async def api_list_entity_relationships(
    slug: str,
    entity_name: str | None = None,
    relationship_type: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    try:
        relationships = await list_project_entity_relationships(
            session,
            slug,
            entity_name=entity_name,
            relationship_type=relationship_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return EntityRelationshipsListResponse(
        relationships=[
            EntityRelationshipResponse.model_validate(item, from_attributes=True)
            for item in relationships
        ],
        total=len(relationships),
    )


@router.get("/insights", response_model=InsightsListResponse)
async def api_list_insights(
    slug: str,
    status: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    try:
        insights = await list_project_insights(session, slug, status=status)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return InsightsListResponse(
        insights=[InsightResponse.model_validate(item, from_attributes=True) for item in insights],
        total=len(insights),
    )


@router.post("/insights/analyze", response_model=AnalyzeResponse)
async def api_analyze_insights(
    slug: str,
    max_age_days: int = 60,
    session: AsyncSession = Depends(get_session),
):
    try:
        result = await analyze_project_insights(session, slug, max_age_days=max_age_days)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AnalyzeResponse(
        contradictions_found=result.contradictions_found,
        staleness_found=result.staleness_found,
        insights_created=result.insights_created,
        insights_skipped=result.insights_skipped,
    )


@router.post("/insights/{insight_id}/status", response_model=InsightResponse)
async def api_update_insight_status(
    slug: str,
    insight_id: str,
    body: InsightStatusUpdate,
    session: AsyncSession = Depends(get_session),
):
    try:
        insight = await update_project_insight_status(
            session,
            slug,
            insight_id=insight_id,
            status=body.status,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail.lower() else 422
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return InsightResponse.model_validate(insight, from_attributes=True)


@router.get("/traceability", response_model=list[TraceabilityChainResponse])
async def api_get_traceability(
    slug: str,
    session: AsyncSession = Depends(get_session),
):
    try:
        chains = await get_traceability_chains(session, slug)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [
        TraceabilityChainResponse(
            requirement=(
                TraceabilityNodeResponse.model_validate(chain.requirement, from_attributes=True)
                if chain.requirement is not None
                else None
            ),
            decisions=[
                TraceabilityNodeResponse.model_validate(item, from_attributes=True)
                for item in chain.decisions
            ],
            schema_entities=[
                TraceabilityNodeResponse.model_validate(item, from_attributes=True)
                for item in chain.schema_entities
            ],
        )
        for chain in chains
    ]
