import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from datum.config import settings
from datum.db import get_session
from datum.schemas.project import ProjectCreate, ProjectResponse
from datum.services.project_manager import create_project, get_project, list_projects
from datum.services.db_sync import sync_project_to_db, log_audit_event
from datum.services.filesystem import compute_content_hash

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


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
