from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from datum.db import get_session
from datum.models.core import Project
from datum.models.operational import SavedSearch
from datum.schemas.saved_search import SavedSearchCreate, SavedSearchResponse

router = APIRouter(prefix="/api/v1/projects/{slug}/saved-searches", tags=["saved-searches"])


async def _get_project(slug: str, session: AsyncSession) -> Project:
    result = await session.execute(select(Project).where(Project.slug == slug))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")
    return project


@router.post("", response_model=SavedSearchResponse, status_code=201)
async def api_create_saved_search(
    slug: str,
    body: SavedSearchCreate,
    session: AsyncSession = Depends(get_session),
):
    project = await _get_project(slug, session)
    record = SavedSearch(
        name=body.name,
        query_text=body.query_text,
        filters=body.filters,
        project_id=project.id,
    )
    session.add(record)
    await session.flush()
    await session.commit()
    return SavedSearchResponse(
        id=str(record.id),
        name=record.name,
        query_text=record.query_text,
        filters=record.filters,
        project_id=str(record.project_id) if record.project_id else None,
        created_at=record.created_at,
    )


@router.get("", response_model=list[SavedSearchResponse])
async def api_list_saved_searches(
    slug: str,
    session: AsyncSession = Depends(get_session),
):
    project = await _get_project(slug, session)
    result = await session.execute(
        select(SavedSearch)
        .where(SavedSearch.project_id == project.id)
        .order_by(SavedSearch.created_at.desc())
    )
    items = result.scalars().all()
    return [
        SavedSearchResponse(
            id=str(item.id),
            name=item.name,
            query_text=item.query_text,
            filters=item.filters,
            project_id=str(item.project_id) if item.project_id else None,
            created_at=item.created_at,
        )
        for item in items
    ]


@router.delete("/{saved_search_id}")
async def api_delete_saved_search(
    slug: str,
    saved_search_id: str,
    session: AsyncSession = Depends(get_session),
):
    project = await _get_project(slug, session)
    record = await session.get(SavedSearch, saved_search_id)
    if record is None or record.project_id != project.id:
        raise HTTPException(status_code=404, detail="Saved search not found")
    await session.delete(record)
    await session.commit()
    return {"status": "deleted"}
