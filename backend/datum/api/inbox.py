from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from datum.db import get_session
from datum.schemas.inbox import (
    AcceptCandidateRequest,
    CandidateActionResponse,
    CandidateResponse,
    EntitySummaryResponse,
    OpenQuestionSummaryResponse,
    ProjectIntelligenceSummaryResponse,
)
from datum.services.delta_aggregator import record_delta
from datum.services.intelligence import (
    CandidateType,
    accept_candidate,
    get_project_intelligence_summary,
    list_candidates,
    reject_candidate,
)
from datum.services.preflight import record_preflight
from datum.services.write_barrier import require_preflight

router = APIRouter(prefix="/api/v1/projects/{slug}", tags=["intelligence"])


@router.get("/inbox", response_model=list[CandidateResponse])
async def api_list_candidates(
    slug: str,
    x_session_id: Annotated[str | None, Header(alias="X-Session-ID")] = None,
    session: AsyncSession = Depends(get_session),
):
    try:
        candidates = await list_candidates(session, slug)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if x_session_id:
        await record_preflight(x_session_id, "list_candidates", session)
        await session.commit()
    return [
        CandidateResponse.model_validate(candidate, from_attributes=True)
        for candidate in candidates
    ]


@router.post(
    "/inbox/{candidate_type}/{candidate_id}/accept",
    response_model=CandidateActionResponse,
)
async def api_accept_candidate(
    slug: str,
    candidate_type: str,
    candidate_id: str,
    body: AcceptCandidateRequest,
    x_session_id: Annotated[str | None, Header(alias="X-Session-ID")] = None,
    session: AsyncSession = Depends(get_session),
    _barrier=Depends(require_preflight),
):
    del _barrier
    if candidate_type not in {"decision", "requirement", "open_question"}:
        raise HTTPException(status_code=400, detail=f"Unknown candidate type: {candidate_type}")
    candidate_kind = cast(CandidateType, candidate_type)

    try:
        result = await accept_candidate(
            session,
            slug=slug,
            candidate_type=candidate_kind,
            candidate_id=candidate_id,
            body=body,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail.lower() or "project" in detail.lower() else 422
        raise HTTPException(status_code=status_code, detail=detail) from exc
    if x_session_id:
        await record_delta(
            x_session_id,
            "candidate_action",
            {"action": "accept", "type": candidate_type, "id": candidate_id},
            session,
        )
        await session.commit()
    return CandidateActionResponse.model_validate(result, from_attributes=True)


@router.post(
    "/inbox/{candidate_type}/{candidate_id}/reject",
    response_model=CandidateActionResponse,
)
async def api_reject_candidate(
    slug: str,
    candidate_type: str,
    candidate_id: str,
    x_session_id: Annotated[str | None, Header(alias="X-Session-ID")] = None,
    session: AsyncSession = Depends(get_session),
    _barrier=Depends(require_preflight),
):
    del _barrier
    if candidate_type not in {"decision", "requirement", "open_question"}:
        raise HTTPException(status_code=400, detail=f"Unknown candidate type: {candidate_type}")
    candidate_kind = cast(CandidateType, candidate_type)

    try:
        result = await reject_candidate(
            session,
            slug=slug,
            candidate_type=candidate_kind,
            candidate_id=candidate_id,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail.lower() or "project" in detail.lower() else 422
        raise HTTPException(status_code=status_code, detail=detail) from exc
    if x_session_id:
        await record_delta(
            x_session_id,
            "candidate_action",
            {"action": "reject", "type": candidate_type, "id": candidate_id},
            session,
        )
        await session.commit()
    return CandidateActionResponse.model_validate(result, from_attributes=True)


@router.get("/intelligence/summary", response_model=ProjectIntelligenceSummaryResponse)
async def api_get_project_intelligence_summary(
    slug: str,
    session: AsyncSession = Depends(get_session),
):
    try:
        summary = await get_project_intelligence_summary(session, slug)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ProjectIntelligenceSummaryResponse(
        pending_candidate_count=summary.pending_candidate_count,
        key_entities=[
            EntitySummaryResponse.model_validate(entity, from_attributes=True)
            for entity in summary.key_entities
        ],
        open_questions=[
            OpenQuestionSummaryResponse.model_validate(question, from_attributes=True)
            for question in summary.open_questions
        ],
    )
