from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from datum.config import settings
from datum.db import get_session
from datum.models.core import Project
from datum.schemas.attachment import AttachmentMoveRequest, AttachmentResponse
from datum.services.attachment_manager import (
    delete_attachment,
    list_attachments,
    move_attachment,
)
from datum.services.db_sync import (
    delete_attachment_in_db,
    log_audit_event,
    move_attachment_in_db,
)
from datum.services.project_manager import get_project

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects/{slug}/attachments", tags=["attachments"])


def _project_path(slug: str):
    project = get_project(settings.projects_root, slug)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")
    return settings.projects_root / slug


async def _project_db_id(slug: str, session: AsyncSession):
    result = await session.execute(select(Project).where(Project.slug == slug))
    project = result.scalar_one_or_none()
    return project.id if project else None


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


@router.get("", response_model=list[AttachmentResponse])
async def api_list_attachments(slug: str):
    project_path = _project_path(slug)
    return [
        AttachmentResponse(**attachment.__dict__)
        for attachment in list_attachments(project_path)
    ]


@router.post("/{attachment_path:path}/move", response_model=AttachmentResponse)
async def api_move_attachment(
    slug: str,
    attachment_path: str,
    body: AttachmentMoveRequest,
    session: AsyncSession = Depends(get_session),
):
    project_path = _project_path(slug)
    try:
        moved = move_attachment(project_path, attachment_path, body.new_relative_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Attachment '{attachment_path}' not found")
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    try:
        project_id = await _project_db_id(slug, session)
        if project_id:
            await move_attachment_in_db(
                session=session,
                project_id=project_id,
                old_filesystem_path=attachment_path,
                new_filesystem_path=moved.relative_path,
            )
            await log_audit_event(
                session,
                "web",
                "move_attachment",
                project_id,
                moved.relative_path,
                metadata={"old_path": attachment_path},
            )
            await session.commit()
    except Exception as exc:
        await session.rollback()
        _log_db_sync_skip(
            operation="move_attachment",
            project_slug=slug,
            canonical_path=moved.relative_path,
            exc=exc,
        )

    return AttachmentResponse(**moved.__dict__)


@router.delete("/{attachment_path:path}", response_model=dict[str, str])
async def api_delete_attachment(
    slug: str,
    attachment_path: str,
    session: AsyncSession = Depends(get_session),
):
    project_path = _project_path(slug)
    try:
        archived_path = delete_attachment(project_path, attachment_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Attachment '{attachment_path}' not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    try:
        project_id = await _project_db_id(slug, session)
        if project_id:
            await delete_attachment_in_db(
                session=session,
                project_id=project_id,
                filesystem_path=attachment_path,
            )
            await log_audit_event(
                session,
                "web",
                "delete_attachment",
                project_id,
                attachment_path,
                metadata={"archived_path": archived_path},
            )
            await session.commit()
    except Exception as exc:
        await session.rollback()
        _log_db_sync_skip(
            operation="delete_attachment",
            project_slug=slug,
            canonical_path=attachment_path,
            exc=exc,
        )

    return {"status": "deleted", "archived_path": archived_path}
