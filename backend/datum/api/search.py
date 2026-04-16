import time
from dataclasses import asdict, is_dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, Header
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from datum.config import settings
from datum.db import get_session
from datum.schemas.search import (
    AnswerModeResponse,
    CitationResponse,
    SearchEntityFacetResponse,
    SearchRequest,
    SearchResponse,
    SearchResultResponse,
    SearchStreamEventResponse,
    SourceRefResponse,
)
from datum.services.answer import generate_answer
from datum.services.model_gateway import build_model_gateway
from datum.services.preflight import record_preflight
from datum.services.search import SearchOptions, search_execution, stream_search

router = APIRouter(prefix="/api/v1", tags=["search"])


def _source_ref_payload(source_ref: object) -> dict:
    if is_dataclass(source_ref):
        return asdict(source_ref)
    if hasattr(source_ref, "__dict__"):
        return vars(source_ref)
    raise TypeError("Unsupported source_ref payload")


def _resolve_search_options(body: SearchRequest) -> tuple[SearchOptions, bool]:
    answer_mode = body.answer_mode or body.mode == "ask_question"
    options = SearchOptions()

    if body.mode == "find_decisions":
        options.allowed_document_types = ("decision",)
        options.max_results_per_document = None
    elif body.mode in {"search_history", "compare_over_time"}:
        options.max_results_per_document = None
        options.rerank_candidate_limit = 75
    elif body.mode == "ask_question":
        options.max_results_per_document = 5

    return options, answer_mode


@router.post("/search", response_model=SearchResponse)
async def api_search(
    body: SearchRequest,
    x_session_id: Annotated[str | None, Header(alias="X-Session-ID")] = None,
    session: AsyncSession = Depends(get_session),
):
    started = time.monotonic()
    effective_limit = min(body.limit, settings.search_result_limit)
    gateway = build_model_gateway()
    search_options, answer_mode = _resolve_search_options(body)
    answer = None
    try:
        execution = await search_execution(
            session=session,
            query=body.query,
            gateway=gateway if (gateway.embedding or gateway.reranker) else None,
            project_scope=body.project,
            version_scope=body.version_scope,
            limit=effective_limit,
            search_options=search_options,
        )
        if answer_mode:
            answer_response = await generate_answer(gateway, body.query, execution.results)
            answer = AnswerModeResponse(
                answer=answer_response.answer,
                citations=[
                    CitationResponse(
                        index=item.index,
                        human_readable=item.human_readable,
                        source_ref=SourceRefResponse(**_source_ref_payload(item.source_ref)),
                    )
                    for item in answer_response.citations
                    if item.source_ref is not None
                ],
                error=answer_response.error,
                model=answer_response.model,
            )
    finally:
        await gateway.close()

    if x_session_id:
        await record_preflight(x_session_id, "search_project_memory", session)
        await session.commit()

    return SearchResponse(
        results=[SearchResultResponse(**asdict(result)) for result in execution.results],
        entity_facets=[
            SearchEntityFacetResponse(**asdict(facet))
            for facet in execution.entity_facets
        ],
        query=body.query,
        result_count=len(execution.results),
        latency_ms=int((time.monotonic() - started) * 1000),
        answer=answer,
    )


@router.post("/search/stream")
async def api_search_stream(
    body: SearchRequest,
    x_session_id: Annotated[str | None, Header(alias="X-Session-ID")] = None,
    session: AsyncSession = Depends(get_session),
):
    effective_limit = min(body.limit, settings.search_result_limit)
    gateway = build_model_gateway()
    search_options, answer_mode = _resolve_search_options(body)

    async def stream():
        last_execution = None
        try:
            async for execution in stream_search(
                session=session,
                query=body.query,
                gateway=gateway if (gateway.embedding or gateway.reranker) else None,
                project_scope=body.project,
                version_scope=body.version_scope,
                limit=effective_limit,
                search_options=search_options,
            ):
                last_execution = execution
                payload = SearchStreamEventResponse(
                    event="phase",
                    phase=execution.phase,
                    query=execution.query,
                    results=[
                        SearchResultResponse(**asdict(result))
                        for result in execution.results
                    ],
                    entity_facets=[
                        SearchEntityFacetResponse(**asdict(facet))
                        for facet in execution.entity_facets
                    ],
                    result_count=len(execution.results),
                    latency_ms=execution.latency_ms,
                    semantic_enabled=execution.semantic_enabled,
                    rerank_applied=execution.rerank_applied,
                )
                yield payload.model_dump_json(exclude_none=True) + "\n"
            if answer_mode and last_execution is not None:
                answer_response = await generate_answer(
                    gateway,
                    body.query,
                    last_execution.results,
                )
                payload = SearchStreamEventResponse(
                    event="phase",
                    phase="answer_ready",
                    query=body.query,
                    results=[
                        SearchResultResponse(**asdict(result))
                        for result in last_execution.results
                    ],
                    entity_facets=[
                        SearchEntityFacetResponse(**asdict(facet))
                        for facet in last_execution.entity_facets
                    ],
                    result_count=len(last_execution.results),
                    latency_ms=last_execution.latency_ms,
                    semantic_enabled=last_execution.semantic_enabled,
                    rerank_applied=last_execution.rerank_applied,
                    answer=AnswerModeResponse(
                        answer=answer_response.answer,
                        citations=[
                            CitationResponse(
                                index=item.index,
                                human_readable=item.human_readable,
                                source_ref=SourceRefResponse(**_source_ref_payload(item.source_ref)),
                            )
                            for item in answer_response.citations
                            if item.source_ref is not None
                        ],
                        error=answer_response.error,
                        model=answer_response.model,
                    ),
                )
                yield payload.model_dump_json(exclude_none=True) + "\n"
        except Exception as exc:
            error_payload = SearchStreamEventResponse(
                event="error",
                query=body.query,
                message=str(exc),
            )
            yield error_payload.model_dump_json(exclude_none=True) + "\n"
        finally:
            await gateway.close()
            if x_session_id:
                await record_preflight(x_session_id, "search_project_memory", session)
                await session.commit()

    return StreamingResponse(stream(), media_type="application/x-ndjson")
