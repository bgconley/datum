import time
from dataclasses import asdict

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from datum.db import get_session
from datum.schemas.search import (
    SearchRequest,
    SearchResponse,
    SearchResultResponse,
    SearchStreamEventResponse,
)
from datum.services.model_gateway import build_model_gateway
from datum.services.search import search, stream_search

router = APIRouter(prefix="/api/v1", tags=["search"])


@router.post("/search", response_model=SearchResponse)
async def api_search(body: SearchRequest, session: AsyncSession = Depends(get_session)):
    started = time.monotonic()
    gateway = build_model_gateway()
    try:
        results = await search(
            session=session,
            query=body.query,
            gateway=gateway if (gateway.embedding or gateway.reranker) else None,
            project_scope=body.project,
            version_scope=body.version_scope,
            limit=body.limit,
        )
    finally:
        await gateway.close()

    return SearchResponse(
        results=[SearchResultResponse(**asdict(result)) for result in results],
        query=body.query,
        result_count=len(results),
        latency_ms=int((time.monotonic() - started) * 1000),
    )


@router.post("/search/stream")
async def api_search_stream(body: SearchRequest, session: AsyncSession = Depends(get_session)):
    gateway = build_model_gateway()

    async def stream():
        try:
            async for execution in stream_search(
                session=session,
                query=body.query,
                gateway=gateway if (gateway.embedding or gateway.reranker) else None,
                project_scope=body.project,
                version_scope=body.version_scope,
                limit=body.limit,
            ):
                payload = SearchStreamEventResponse(
                    event="phase",
                    phase=execution.phase,
                    query=execution.query,
                    results=[
                        SearchResultResponse(**asdict(result))
                        for result in execution.results
                    ],
                    result_count=len(execution.results),
                    latency_ms=execution.latency_ms,
                    semantic_enabled=execution.semantic_enabled,
                    rerank_applied=execution.rerank_applied,
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

    return StreamingResponse(stream(), media_type="application/x-ndjson")
