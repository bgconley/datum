"""Project context API endpoint for token-budgeted agent context."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query

from datum.config import settings
from datum.models.agent import ApiKey
from datum.services.auth import extract_api_key
from datum.services.boundaries import ContentKind, wrap_content
from datum.services.context import ContextConfig, DetailLevel, build_project_context

router = APIRouter(prefix="/api/v1/projects/{slug}/context", tags=["context"])


@router.get("")
async def api_get_project_context(
    slug: str,
    detail: str = Query("standard"),
    max_tokens: int = Query(8000, ge=100, le=100000),
    recency_days: int | None = Query(None, ge=0),
    limit_per_section: int | None = Query(None, ge=1),
    api_key: ApiKey | None = Depends(extract_api_key),
):
    del api_key  # Optional in Phase 6 for backward compatibility.

    project_dir = settings.projects_root / slug
    if not project_dir.exists():
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")

    try:
        detail_level = DetailLevel(detail)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid detail level: {detail}") from exc

    payload = build_project_context(
        project_dir,
        ContextConfig(
            detail=detail_level,
            max_tokens=max_tokens,
            recency_days=recency_days,
            limit_per_section=limit_per_section,
        ),
    )
    return wrap_content(json.dumps(payload, default=str), ContentKind.DOCUMENT) | {"data": payload}
