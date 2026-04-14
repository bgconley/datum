import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from datum.config import settings
from datum.db import get_session
from datum.models.core import Project
from datum.schemas.document import (
    DocumentContentResponse,
    DocumentCreate,
    DocumentMoveRequest,
    DocumentResponse,
    DocumentSave,
    FolderCreateRequest,
    GeneratedFileResponse,
)
from datum.services.db_sync import (
    log_audit_event,
    move_document_path_in_db,
    soft_delete_document_in_db,
    sync_document_version_to_db,
)
from datum.services.document_manager import (
    ConflictError,
    create_document,
    create_document_folder,
    delete_document,
    get_document,
    list_documents,
    move_document,
    save_document,
)
from datum.services.filesystem import ManifestLayoutConflictError
from datum.services.project_manager import get_project
from datum.services.versioning import StalePendingCommitError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects/{slug}/docs", tags=["documents"])


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


def _get_project_path(slug: str):
    try:
        info = get_project(settings.projects_root, slug)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not info:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")
    return settings.projects_root / slug


async def _get_project_db_id(slug: str, session: AsyncSession):
    """Look up project DB id. Returns None if DB is unavailable or project not synced."""
    try:
        result = await session.execute(select(Project).where(Project.slug == slug))
        project = result.scalar_one_or_none()
        return project.id if project else None
    except Exception:
        return None


async def _get_document_version_id(
    slug: str,
    canonical_path: str,
    session: AsyncSession,
) -> str | None:
    try:
        project_result = await session.execute(select(Project).where(Project.slug == slug))
        project = project_result.scalar_one_or_none()
        if project is None:
            return None
        from datum.models.core import Document

        result = await session.execute(
            select(Document.current_version_id).where(
                Document.project_id == project.id,
                Document.canonical_path == canonical_path,
            )
        )
        current_version_id = result.scalar_one_or_none()
        return str(current_version_id) if current_version_id else None
    except Exception:
        return None


@router.get("", response_model=list[DocumentResponse])
async def api_list_documents(slug: str):
    project_path = _get_project_path(slug)
    try:
        docs = list_documents(project_path)
    except ManifestLayoutConflictError as e:
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Manifest layout conflict — run datum doctor or migration to resolve",
                "canonical_path": e.canonical_path,
            },
        )
    return [DocumentResponse(**d.__dict__) for d in docs]


@router.post("", response_model=DocumentResponse, status_code=201)
async def api_create_document(
    slug: str, body: DocumentCreate, session: AsyncSession = Depends(get_session)
):
    project_path = _get_project_path(slug)
    try:
        doc_info = create_document(
            project_path=project_path,
            relative_path=body.relative_path,
            title=body.title,
            doc_type=body.doc_type,
            content=body.content,
            tags=body.tags,
            status=body.status,
        )
    except FileExistsError:
        raise HTTPException(
            status_code=409,
            detail=f"Document '{body.relative_path}' already exists",
        )
    except StalePendingCommitError as e:
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Document has a stale pending commit requiring reconciler recovery",
                "canonical_path": e.canonical_path,
                "stale_version": e.version,
            },
        )
    except ManifestLayoutConflictError as e:
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Manifest layout conflict — run datum doctor or migration to resolve",
                "canonical_path": e.canonical_path,
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # DB catch-up (best-effort)
    try:
        project_db_id = await _get_project_db_id(slug, session)
        if project_db_id:
            canonical_path = doc_info.relative_path
            from datum.services.versioning import get_current_version

            ver = get_current_version(project_path, canonical_path)
            if ver:
                file_bytes = (project_path / canonical_path).read_bytes()
                await sync_document_version_to_db(
                    session=session,
                    project_id=project_db_id,
                    version_info=ver,
                    canonical_path=canonical_path,
                    title=doc_info.title,
                    doc_type=doc_info.doc_type,
                    status=doc_info.status,
                    tags=doc_info.tags,
                    change_source="web",
                    content_hash=doc_info.content_hash,
                    byte_size=len(file_bytes),
                    filesystem_path=ver.version_file,
                )
                await log_audit_event(
                    session,
                    "web",
                    "create_document",
                    project_db_id,
                    canonical_path,
                    new_hash=doc_info.content_hash,
                )
                await session.commit()
    except Exception as exc:
        await session.rollback()
        _log_db_sync_skip(
            operation="create_document",
            project_slug=slug,
            canonical_path=doc_info.relative_path,
            exc=exc,
        )

    return DocumentResponse(**doc_info.__dict__)


@router.post("/folders", response_model=dict[str, str], status_code=201)
async def api_create_folder(slug: str, body: FolderCreateRequest):
    project_path = _get_project_path(slug)
    try:
        relative_path = create_document_folder(project_path, body.relative_path)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"relative_path": relative_path}


@router.get("/generated", response_model=list[GeneratedFileResponse])
async def api_list_generated_files(slug: str):
    project_path = _get_project_path(slug)
    generated_root = project_path / ".piq"
    if not generated_root.exists():
        return []

    files: list[GeneratedFileResponse] = []
    for path in sorted(generated_root.rglob("*")):
        if not path.is_file():
            continue
        relative_path = path.relative_to(project_path).as_posix()
        files.append(
            GeneratedFileResponse(
                relative_path=relative_path,
                absolute_path=str(path),
                size_bytes=path.stat().st_size,
            )
        )
    return files


@router.post("/{doc_path:path}/move", response_model=DocumentResponse)
async def api_move_document(
    slug: str,
    doc_path: str,
    body: DocumentMoveRequest,
    session: AsyncSession = Depends(get_session),
):
    project_path = _get_project_path(slug)
    try:
        original = get_document(project_path, doc_path)
        if original is None:
            raise FileNotFoundError(f"Document '{doc_path}' not found")
        doc_info = move_document(project_path, doc_path, body.new_relative_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Document '{doc_path}' not found")
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ManifestLayoutConflictError as e:
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Manifest layout conflict — run datum doctor or migration to resolve",
                "canonical_path": e.canonical_path,
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        project_db_id = await _get_project_db_id(slug, session)
        if project_db_id and original is not None:
            await move_document_path_in_db(
                session=session,
                project_id=project_db_id,
                old_canonical_path=original.relative_path,
                new_canonical_path=doc_info.relative_path,
            )
            await log_audit_event(
                session,
                "web",
                "move_document",
                project_db_id,
                doc_info.relative_path,
                old_hash=original.content_hash,
                new_hash=doc_info.content_hash,
            )
            await session.commit()
    except Exception as exc:
        await session.rollback()
        _log_db_sync_skip(
            operation="move_document",
            project_slug=slug,
            canonical_path=doc_info.relative_path,
            exc=exc,
        )

    return DocumentResponse(**doc_info.__dict__)


@router.get("/{doc_path:path}", response_model=DocumentContentResponse)
async def api_get_document(
    slug: str,
    doc_path: str,
    session: AsyncSession = Depends(get_session),
):
    project_path = _get_project_path(slug)
    try:
        info = get_document(project_path, doc_path)
    except ManifestLayoutConflictError as e:
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Manifest layout conflict — run datum doctor or migration to resolve",
                "canonical_path": e.canonical_path,
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not info:
        raise HTTPException(status_code=404, detail=f"Document '{doc_path}' not found")
    content = (project_path / info.relative_path).read_text()
    metadata = DocumentResponse(
        **info.__dict__,
        version_id=await _get_document_version_id(slug, info.relative_path, session),
    )
    return DocumentContentResponse(content=content, metadata=metadata)


@router.put("/{doc_path:path}", response_model=DocumentResponse)
async def api_save_document(
    slug: str, doc_path: str, body: DocumentSave,
    session: AsyncSession = Depends(get_session),
):
    project_path = _get_project_path(slug)
    old_hash = body.base_hash
    try:
        doc_info = save_document(
            project_path=project_path,
            relative_path=doc_path,
            content=body.content,
            base_hash=body.base_hash,
            change_source="web",
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Document '{doc_path}' not found")
    except StalePendingCommitError as e:
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Document has a stale pending commit requiring reconciler recovery",
                "canonical_path": e.canonical_path,
                "stale_version": e.version,
            },
        )
    except ManifestLayoutConflictError as e:
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Manifest layout conflict — run datum doctor or migration to resolve",
                "canonical_path": e.canonical_path,
            },
        )
    except ConflictError as e:
        raise HTTPException(
            status_code=409,
            detail={"message": "Document modified since last load", "current_hash": e.current_hash},
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # DB catch-up (best-effort)
    try:
        project_db_id = await _get_project_db_id(slug, session)
        if project_db_id:
            canonical_path = doc_info.relative_path
            from datum.services.versioning import get_current_version

            ver = get_current_version(project_path, canonical_path)
            if ver:
                file_bytes = (project_path / canonical_path).read_bytes()
                await sync_document_version_to_db(
                    session=session,
                    project_id=project_db_id,
                    version_info=ver,
                    canonical_path=canonical_path,
                    title=doc_info.title,
                    doc_type=doc_info.doc_type,
                    status=doc_info.status,
                    tags=doc_info.tags,
                    change_source="web",
                    content_hash=doc_info.content_hash,
                    byte_size=len(file_bytes),
                    filesystem_path=ver.version_file,
                )
                await log_audit_event(
                    session, "web", "save_document", project_db_id,
                    canonical_path, old_hash=old_hash, new_hash=doc_info.content_hash,
                )
                await session.commit()
    except Exception as exc:
        await session.rollback()
        _log_db_sync_skip(
            operation="save_document",
            project_slug=slug,
            canonical_path=doc_info.relative_path,
            exc=exc,
        )

    return DocumentResponse(**doc_info.__dict__)


@router.delete("/{doc_path:path}")
async def api_delete_document(
    slug: str,
    doc_path: str,
    session: AsyncSession = Depends(get_session),
):
    project_path = _get_project_path(slug)
    try:
        archived_path = delete_document(project_path, doc_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Document '{doc_path}' not found")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        project_db_id = await _get_project_db_id(slug, session)
        if project_db_id:
            await soft_delete_document_in_db(session, project_db_id, doc_path)
            await log_audit_event(
                session,
                "web",
                "delete_document",
                project_db_id,
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
