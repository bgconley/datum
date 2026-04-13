import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from datum.config import settings
from datum.db import get_session
from datum.schemas.document import DocumentResponse, GeneratedFileResponse
from datum.schemas.project import ProjectCreate, ProjectResponse, WorkspaceSnapshotResponse
from datum.services.db_sync import log_audit_event, sync_project_to_db
from datum.services.document_manager import list_documents
from datum.services.filesystem import compute_content_hash
from datum.services.project_manager import create_project, get_project, list_projects

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])
ws_router = APIRouter(prefix="/ws/projects", tags=["projects"])


def _list_generated_files(project_path: Path) -> list[GeneratedFileResponse]:
    generated_root = project_path / ".piq"
    if not generated_root.exists():
        return []

    files: list[GeneratedFileResponse] = []
    for path in sorted(generated_root.rglob("*")):
        if not path.is_file():
            continue
        files.append(
            GeneratedFileResponse(
                relative_path=path.relative_to(project_path).as_posix(),
                absolute_path=str(path),
                size_bytes=path.stat().st_size,
            )
        )
    return files


def _workspace_snapshot(slug: str) -> WorkspaceSnapshotResponse:
    try:
        project = get_project(settings.projects_root, slug)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")

    project_path = settings.projects_root / slug
    documents = [DocumentResponse(**doc.__dict__) for doc in list_documents(project_path)]
    generated_files = _list_generated_files(project_path)
    return WorkspaceSnapshotResponse(
        project=ProjectResponse(**project.__dict__),
        documents=documents,
        generated_files=generated_files,
    )


@router.get("", response_model=list[ProjectResponse])
async def api_list_projects():
    projects = list_projects(settings.projects_root)
    return [ProjectResponse(**p.__dict__) for p in projects]


@router.post("", response_model=ProjectResponse, status_code=201)
async def api_create_project(body: ProjectCreate, session: AsyncSession = Depends(get_session)):
    try:
        info = create_project(
            projects_root=settings.projects_root,
            name=body.name,
            slug=body.slug,
            description=body.description,
            tags=body.tags,
        )
    except (FileExistsError, ValueError) as e:
        status = 409 if isinstance(e, FileExistsError) else 422
        raise HTTPException(status_code=status, detail=str(e))

    # DB catch-up (best-effort — filesystem is canonical)
    try:
        project_yaml = (settings.projects_root / body.slug / "project.yaml").read_bytes()
        project_db_id = await sync_project_to_db(
            session=session,
            uid=info.uid,
            slug=info.slug,
            name=info.name,
            filesystem_path=str(settings.projects_root / body.slug),
            project_yaml_hash=compute_content_hash(project_yaml),
            description=info.description,
            tags=info.tags,
        )
        await log_audit_event(session, "web", "create_project", project_db_id, info.slug)
    except Exception:
        logger.debug("DB sync skipped (no database connection)", exc_info=True)

    return ProjectResponse(**info.__dict__)


@router.get("/{slug}", response_model=ProjectResponse)
async def api_get_project(slug: str):
    try:
        info = get_project(settings.projects_root, slug)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not info:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")
    return ProjectResponse(**info.__dict__)


@router.get("/{slug}/workspace", response_model=WorkspaceSnapshotResponse)
async def api_get_project_workspace(slug: str):
    return _workspace_snapshot(slug)


@ws_router.websocket("/{slug}/workspace")
async def ws_project_workspace(slug: str, websocket: WebSocket):
    await websocket.accept()
    last_payload: str | None = None

    try:
        while True:
            try:
                payload = _workspace_snapshot(slug)
            except HTTPException as exc:
                await websocket.close(code=1008, reason=str(exc.detail))
                return

            serialized = payload.model_dump_json()
            if serialized != last_payload:
                await websocket.send_text(serialized)
                last_payload = serialized

            await asyncio.sleep(2)
    except WebSocketDisconnect:
        return
