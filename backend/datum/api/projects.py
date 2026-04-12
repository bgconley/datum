from fastapi import APIRouter, HTTPException

from datum.config import settings
from datum.schemas.project import ProjectCreate, ProjectResponse
from datum.services.project_manager import create_project, get_project, list_projects

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.get("", response_model=list[ProjectResponse])
async def api_list_projects():
    projects = list_projects(settings.projects_root)
    return [ProjectResponse(**p.__dict__) for p in projects]


@router.post("", response_model=ProjectResponse, status_code=201)
async def api_create_project(body: ProjectCreate):
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
