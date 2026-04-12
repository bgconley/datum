from fastapi import APIRouter, HTTPException

from datum.config import settings
from datum.schemas.document import (
    DocumentContentResponse,
    DocumentCreate,
    DocumentResponse,
    DocumentSave,
)
from datum.services.document_manager import (
    ConflictError,
    create_document,
    get_document,
    list_documents,
    save_document,
)
from datum.services.project_manager import get_project

router = APIRouter(prefix="/api/v1/projects/{slug}/docs", tags=["documents"])


def _get_project_path(slug: str):
    try:
        info = get_project(settings.projects_root, slug)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not info:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")
    return settings.projects_root / slug


@router.get("", response_model=list[DocumentResponse])
async def api_list_documents(slug: str):
    project_path = _get_project_path(slug)
    docs = list_documents(project_path)
    return [DocumentResponse(**d.__dict__) for d in docs]


@router.post("", response_model=DocumentResponse, status_code=201)
async def api_create_document(slug: str, body: DocumentCreate):
    project_path = _get_project_path(slug)
    try:
        info = create_document(
            project_path=project_path,
            relative_path=body.relative_path,
            title=body.title,
            doc_type=body.doc_type,
            content=body.content,
            tags=body.tags,
            status=body.status,
        )
    except FileExistsError:
        raise HTTPException(status_code=409, detail=f"Document '{body.relative_path}' already exists")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return DocumentResponse(**info.__dict__)


@router.get("/{doc_path:path}", response_model=DocumentContentResponse)
async def api_get_document(slug: str, doc_path: str):
    project_path = _get_project_path(slug)
    try:
        info = get_document(project_path, doc_path)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not info:
        raise HTTPException(status_code=404, detail=f"Document '{doc_path}' not found")
    content = (project_path / doc_path).read_text()
    return DocumentContentResponse(content=content, metadata=DocumentResponse(**info.__dict__))


@router.put("/{doc_path:path}", response_model=DocumentResponse)
async def api_save_document(slug: str, doc_path: str, body: DocumentSave):
    project_path = _get_project_path(slug)
    try:
        info = save_document(
            project_path=project_path,
            relative_path=doc_path,
            content=body.content,
            base_hash=body.base_hash,
            change_source="web",
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Document '{doc_path}' not found")
    except ConflictError as e:
        raise HTTPException(
            status_code=409,
            detail={"message": "Document modified since last load", "current_hash": e.current_hash},
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return DocumentResponse(**info.__dict__)
