"""Session note API endpoints for agent workflows."""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from datum.config import settings
from datum.db import get_session
from datum.models.agent import ApiKey
from datum.models.core import Document, Project
from datum.schemas.agent import (
    SessionAppendRequest,
    SessionCreateRequest,
    SessionListItem,
    SessionListResponse,
    SessionResponse,
)
from datum.services.audit import log_agent_audit
from datum.services.auth import extract_api_key
from datum.services.db_sync import sync_document_version_to_db
from datum.services.idempotency import check_idempotency, store_idempotency
from datum.services.session_links import auto_link_session_note
from datum.services.sessions import (
    SessionMetadata,
    append_session_note,
    find_session_note,
    list_session_notes,
    parse_session_frontmatter,
)
from datum.services.sessions import create_session_note as create_session_note_file
from datum.services.versioning import get_current_version

router = APIRouter(prefix="/api/v1/projects/{slug}/sessions", tags=["sessions"])


def _get_project_dir(slug: str):
    project_dir = settings.projects_root / slug
    if not project_dir.exists():
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")
    return project_dir


async def _get_project_row(slug: str, session: AsyncSession) -> Project | None:
    result = await session.execute(select(Project).where(Project.slug == slug))
    return result.scalar_one_or_none()


def _stable_json_response(status_code: int, body: dict) -> Response:
    return Response(
        content=json.dumps(body, sort_keys=True, separators=(",", ":")),
        media_type="application/json",
        status_code=status_code,
    )


async def _sync_session_note(
    *,
    slug: str,
    session: AsyncSession,
    relative_path: str,
    meta: SessionMetadata,
) -> None:
    project_row = await _get_project_row(slug, session)
    if project_row is None:
        return

    project_dir = settings.projects_root / slug
    version = get_current_version(project_dir, relative_path)
    if version is None:
        return

    file_bytes = (project_dir / relative_path).read_bytes()
    await sync_document_version_to_db(
        session=session,
        project_id=project_row.id,
        version_info=version,
        canonical_path=relative_path,
        title=meta.summary,
        doc_type="session",
        status="complete" if meta.ended_at else "active",
        tags=[],
        change_source="agent",
        content_hash=version.content_hash,
        byte_size=len(file_bytes),
        filesystem_path=version.version_file,
    )
    doc_result = await session.execute(
        select(Document).where(
            Document.project_id == project_row.id,
            Document.canonical_path == relative_path,
        )
    )
    document_row = doc_result.scalar_one_or_none()
    if document_row is not None and document_row.current_version_id is not None:
        await auto_link_session_note(
            session,
            project_id=project_row.id,
            version_id=document_row.current_version_id,
            content=meta.content,
        )


@router.post("", status_code=201, response_model=SessionResponse)
async def api_create_session(
    slug: str,
    body: SessionCreateRequest,
    session: AsyncSession = Depends(get_session),
    api_key: ApiKey | None = Depends(extract_api_key),
    idempotency_key: Annotated[str | None, Header(alias="X-Idempotency-Key")] = None,
):
    del api_key  # Optional in Phase 6 for backward compatibility.

    project_dir = _get_project_dir(slug)
    scope = "create_session_note"
    if idempotency_key:
        cached = await check_idempotency(session, idempotency_key, scope=scope)
        if cached is not None:
            return _stable_json_response(cached["status_code"], cached["body"])

    existing = find_session_note(project_dir, body.session_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"Session '{body.session_id}' already exists")

    meta = SessionMetadata(
        session_id=body.session_id,
        agent_name=body.agent_name,
        summary=body.summary,
        content=body.content,
        repo_path=body.repo_path,
        git_branch=body.git_branch,
        git_commit=body.git_commit,
        files_touched=body.files_touched,
        commands_run=body.commands_run,
        next_steps=body.next_steps,
    )
    created_path = create_session_note_file(project_dir, meta)
    relative_path = created_path.relative_to(project_dir).as_posix()
    version = get_current_version(project_dir, relative_path)
    project_row = await _get_project_row(slug, session)

    await _sync_session_note(
        slug=slug,
        session=session,
        relative_path=relative_path,
        meta=meta,
    )
    await log_agent_audit(
        session,
        actor_type="agent",
        actor_name=body.agent_name,
        operation="create_session_note",
        project_id=project_row.id if project_row else None,
        target_path=relative_path,
        new_hash=version.content_hash if version else None,
        metadata={"session_id": body.session_id, "idempotency_key": idempotency_key},
    )

    response = SessionResponse(
        session_id=body.session_id,
        path=relative_path,
        agent_name=body.agent_name,
        summary=body.summary,
    ).model_dump()
    if idempotency_key:
        await store_idempotency(session, idempotency_key, scope, 201, response)
    await session.commit()
    return _stable_json_response(201, response)


@router.put("/{session_id}")
async def api_append_session(
    slug: str,
    session_id: str,
    body: SessionAppendRequest,
    session: AsyncSession = Depends(get_session),
    api_key: ApiKey | None = Depends(extract_api_key),
    idempotency_key: Annotated[str | None, Header(alias="X-Idempotency-Key")] = None,
):
    del api_key

    project_dir = _get_project_dir(slug)
    scope = "append_session_note"
    if idempotency_key:
        cached = await check_idempotency(session, idempotency_key, scope=scope)
        if cached is not None:
            return _stable_json_response(cached["status_code"], cached["body"])

    session_file = find_session_note(project_dir, session_id)
    if session_file is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    existing_meta = parse_session_frontmatter(session_file.read_text())
    append_session_note(
        project_dir,
        session_file,
        new_content=body.content,
        new_files=body.files_touched,
        new_commands=body.commands_run,
        new_next_steps=body.next_steps,
        updated_summary=body.summary,
    )
    updated_meta = parse_session_frontmatter(session_file.read_text())
    relative_path = session_file.relative_to(project_dir).as_posix()
    project_row = await _get_project_row(slug, session)

    await _sync_session_note(
        slug=slug,
        session=session,
        relative_path=relative_path,
        meta=updated_meta,
    )
    version = get_current_version(project_dir, relative_path)
    await log_agent_audit(
        session,
        actor_type="agent",
        actor_name=existing_meta.agent_name or updated_meta.agent_name,
        operation="append_session_note",
        project_id=project_row.id if project_row else None,
        target_path=relative_path,
        new_hash=version.content_hash if version else None,
        metadata={"session_id": session_id, "idempotency_key": idempotency_key},
    )

    response = {
        "status": "appended",
        "session_id": session_id,
        "path": relative_path,
    }
    if idempotency_key:
        await store_idempotency(session, idempotency_key, scope, 200, response)
    await session.commit()
    return _stable_json_response(200, response)


@router.get("", response_model=SessionListResponse)
async def api_list_sessions(
    slug: str,
    api_key: ApiKey | None = Depends(extract_api_key),
):
    del api_key

    project_dir = _get_project_dir(slug)
    items = [
        SessionListItem(**item)
        for item in list_session_notes(project_dir)
    ]
    return SessionListResponse(sessions=items)
