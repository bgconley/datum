"""Citation resolution API for exact source retrieval."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from datum.config import settings
from datum.models.agent import ApiKey
from datum.schemas.agent import CitationResolveRequest, CitationResolveResponse
from datum.services.auth import extract_api_key
from datum.services.boundaries import ContentKind, wrap_content
from datum.services.citations import SourceRef, resolve_citation
from datum.services.filesystem import resolve_manifest_dir

router = APIRouter(prefix="/api/v1/citations", tags=["citations"])


@router.post("/resolve", response_model=CitationResolveResponse)
async def api_resolve_citation(
    body: CitationResolveRequest,
    api_key: ApiKey | None = Depends(extract_api_key),
):
    del api_key  # Optional in Phase 6 for backward compatibility.

    ref = SourceRef(**body.source_ref.model_dump())
    project_dir = settings.projects_root / ref.project_slug
    if not project_dir.exists():
        return CitationResolveResponse(error=f"Project '{ref.project_slug}' not found")
    manifest_dir = resolve_manifest_dir(project_dir, ref.canonical_path, for_write=False)
    content = resolve_citation(ref, manifest_dir)
    if content is None:
        return CitationResolveResponse(error="Citation source not found")

    wrapped = wrap_content(content, ContentKind.DOCUMENT, project_slug=ref.project_slug)
    return CitationResolveResponse(**wrapped)
