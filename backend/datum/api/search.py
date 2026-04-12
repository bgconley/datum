from dataclasses import asdict
import time

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from datum.db import get_session
from datum.schemas.search import SearchRequest, SearchResponse, SearchResultResponse
from datum.services.model_gateway import build_model_gateway
from datum.services.search import search

router = APIRouter(prefix="/api/v1", tags=["search"])


@router.post("/search", response_model=SearchResponse)
async def api_search(body: SearchRequest, session: AsyncSession = Depends(get_session)):
    started = time.monotonic()
    gateway = build_model_gateway()
    try:
        results = await search(
            session=session,
            query=body.query,
            gateway=gateway if gateway.embedding else None,
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
