from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from datum.config import settings
from datum.db import get_session
from datum.models.core import Project
from datum.services.db_sync import (
    log_audit_event,
    move_document_path_in_db,
    soft_delete_document_in_db,
)
from datum.services.document_manager import (
    create_document_folder,
    delete_document,
    move_document,
)
from datum.services.project_manager import get_project

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects/{slug}/fs", tags=["filesystem"])


def _log_db_sync_skip(
    *,
    operation: str,
    project_slug: str,
    canonical_path: str,
    exc: Exception,
) -> None:
    logger.warning(
        "DB sync skipped for %s (project=%s, path=%s): %s",
        operation,
        project_slug,
        canonical_path,
        exc,
        exc_info=True,
    )


class RenameRequest(BaseModel):
    old_path: str
    new_path: str


class MkdirRequest(BaseModel):
    path: str


def _project_path(slug: str):
    project = get_project(settings.projects_root, slug)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")
    return settings.projects_root / slug


async def _project_db_id(slug: str, session: AsyncSession):
    result = await session.execute(select(Project).where(Project.slug == slug))
    project = result.scalar_one_or_none()
    return project.id if project else None


@router.post("/rename")
async def api_rename_document(
    slug: str,
    body: RenameRequest,
    session: AsyncSession = Depends(get_session),
):
    project_path = _project_path(slug)
    try:
        moved = move_document(project_path, body.old_path, body.new_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Document '{body.old_path}' not found")
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    try:
        project_id = await _project_db_id(slug, session)
        if project_id:
            await move_document_path_in_db(session, project_id, body.old_path, moved.relative_path)
            await log_audit_event(
                session,
                "web",
                "rename_document",
                project_id,
                moved.relative_path,
                metadata={"old_path": body.old_path},
            )
            await session.commit()
    except Exception as exc:
        await session.rollback()
        _log_db_sync_skip(
            operation="rename_document",
            project_slug=slug,
            canonical_path=moved.relative_path,
            exc=exc,
        )

    return {"old_path": body.old_path, "new_path": moved.relative_path}


@router.delete("/{doc_path:path}")
async def api_delete_document(
    slug: str,
    doc_path: str,
    session: AsyncSession = Depends(get_session),
):
    project_path = _project_path(slug)
    try:
        archived_path = delete_document(project_path, doc_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Document '{doc_path}' not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    try:
        project_id = await _project_db_id(slug, session)
        if project_id:
            await soft_delete_document_in_db(session, project_id, doc_path)
            await log_audit_event(
                session,
                "web",
                "delete_document",
                project_id,
                doc_path,
                metadata={"archived_path": archived_path},
            )
            await session.commit()
    except Exception as exc:
        await session.rollback()
        _log_db_sync_skip(
            operation="delete_document",
            project_slug=slug,
            canonical_path=doc_path,
            exc=exc,
        )

    return {"status": "deleted", "archived_path": archived_path}


@router.post("/mkdir", status_code=201)
async def api_mkdir(
    slug: str,
    body: MkdirRequest,
    session: AsyncSession = Depends(get_session),
):
    project_path = _project_path(slug)
    try:
        relative_path = create_document_folder(project_path, body.path)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    try:
        project_id = await _project_db_id(slug, session)
        if project_id:
            await log_audit_event(session, "web", "mkdir", project_id, relative_path)
            await session.commit()
    except Exception as exc:
        await session.rollback()
        _log_db_sync_skip(
            operation="mkdir",
            project_slug=slug,
            canonical_path=relative_path,
            exc=exc,
        )

    return {"path": relative_path}
