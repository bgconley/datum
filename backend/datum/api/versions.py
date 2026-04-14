import difflib
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from datum.config import settings
from datum.db import get_session
from datum.models.core import Document, DocumentVersion, Project
from datum.models.search import IngestionJob
from datum.schemas.document import DocumentResponse
from datum.schemas.version import (
    VersionContentResponse,
    VersionDiffResponse,
    VersionResponse,
    VersionRestoreRequest,
)
from datum.services.db_sync import log_audit_event, sync_document_version_to_db
from datum.services.document_manager import (
    _validate_document_path,
    get_document,
    restore_document_version,
)
from datum.services.filesystem import compute_content_hash
from datum.services.project_manager import get_project
from datum.services.versioning import get_current_version, list_versions, read_version_content

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/projects/{slug}/docs/{doc_path:path}/versions",
    tags=["versions"],
)


def _get_project_path(slug: str) -> Path:
    try:
        info = get_project(settings.projects_root, slug)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not info:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")
    return settings.projects_root / slug


def _normalize_document_path(doc_path: str) -> str:
    try:
        return _validate_document_path(doc_path)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


async def _get_project_db_id(slug: str, session: AsyncSession):
    result = await session.execute(select(Project).where(Project.slug == slug))
    project = result.scalar_one_or_none()
    return project.id if project else None


async def _load_version_metadata(
    session: AsyncSession,
    project_slug: str,
    document_uid: str,
) -> dict[tuple[str, int], tuple[str | None, str | None]]:
    """Return {(branch, version_number): (created_by, indexing_status)}."""
    project_result = await session.execute(select(Project).where(Project.slug == project_slug))
    project = project_result.scalar_one_or_none()
    if project is None:
        return {}

    document_result = await session.execute(
        select(Document).where(
            Document.project_id == project.id,
            Document.uid == document_uid,
        )
    )
    document = document_result.scalar_one_or_none()
    if document is None:
        return {}

    version_result = await session.execute(
        select(DocumentVersion).where(DocumentVersion.document_id == document.id)
    )
    versions = version_result.scalars().all()
    if not versions:
        return {}

    version_ids = [version.id for version in versions]
    job_result = await session.execute(
        select(IngestionJob).where(IngestionJob.version_id.in_(version_ids))
    )
    jobs = job_result.scalars().all()

    jobs_by_version: dict[object, list[IngestionJob]] = {}
    for job in jobs:
        jobs_by_version.setdefault(job.version_id, []).append(job)

    metadata: dict[tuple[str, int], tuple[str | None, str | None]] = {}
    for version in versions:
        version_jobs = jobs_by_version.get(version.id, [])
        statuses = {job.status for job in version_jobs}
        if not version_jobs:
            indexing_status = "pending"
        elif "failed" in statuses:
            indexing_status = "failed"
        elif any(status in {"queued", "running"} for status in statuses):
            indexing_status = "processing"
        elif statuses and statuses <= {"completed", "skipped"}:
            indexing_status = "indexed"
        else:
            indexing_status = "pending"

        metadata[(version.branch, version.version_number)] = (
            version.agent_name or version.change_source,
            indexing_status,
        )

    return metadata


@router.get("", response_model=list[VersionResponse])
async def api_list_versions(
    slug: str,
    doc_path: str,
    branch: str = "main",
    session: AsyncSession = Depends(get_session),
):
    project_path = _get_project_path(slug)
    canonical_path = _normalize_document_path(doc_path)
    versions = list_versions(project_path, canonical_path, branch=branch)
    if not versions:
        raise HTTPException(
            status_code=404,
            detail=f"No versions found for '{canonical_path}'",
        )
    metadata_map: dict[tuple[str, int], tuple[str | None, str | None]] = {}
    try:
        metadata_map = await _load_version_metadata(session, slug, versions[0].document_uid)
    except Exception:
        logger.debug("Version metadata enrichment skipped", exc_info=True)

    return [
        VersionResponse(
            version_number=version.version_number,
            branch=version.branch,
            content_hash=version.content_hash,
            version_file=version.version_file,
            document_uid=version.document_uid,
            created_at=version.created_at.isoformat(),
            label=version.label,
            change_source=version.change_source,
            restored_from=version.restored_from,
            created_by=(
                metadata_map.get((version.branch, version.version_number), (None, None))[0]
                or version.change_source
            ),
            indexing_status=metadata_map.get(
                (version.branch, version.version_number),
                (None, None),
            )[1],
        )
        for version in versions
    ]


@router.get("/{version_number}", response_model=VersionContentResponse)
async def api_get_version_content(
    slug: str,
    doc_path: str,
    version_number: int,
    branch: str = "main",
):
    project_path = _get_project_path(slug)
    canonical_path = _normalize_document_path(doc_path)
    content_bytes = read_version_content(
        project_path,
        canonical_path,
        version_number,
        branch=branch,
    )
    if content_bytes is None:
        raise HTTPException(status_code=404, detail=f"Version {version_number} not found")

    return VersionContentResponse(
        version_number=version_number,
        content=content_bytes.decode("utf-8", errors="replace"),
        content_hash=compute_content_hash(content_bytes),
    )


@router.get("/diff/{version_a}/{version_b}", response_model=VersionDiffResponse)
async def api_diff_versions(
    slug: str,
    doc_path: str,
    version_a: int,
    version_b: int,
    branch: str = "main",
):
    project_path = _get_project_path(slug)
    canonical_path = _normalize_document_path(doc_path)
    content_a = read_version_content(project_path, canonical_path, version_a, branch=branch)
    content_b = read_version_content(project_path, canonical_path, version_b, branch=branch)

    if content_a is None:
        raise HTTPException(status_code=404, detail=f"Version {version_a} not found")
    if content_b is None:
        raise HTTPException(status_code=404, detail=f"Version {version_b} not found")

    lines_a = content_a.decode("utf-8", errors="replace").splitlines(keepends=True)
    lines_b = content_b.decode("utf-8", errors="replace").splitlines(keepends=True)

    diff_lines = list(
        difflib.unified_diff(
            lines_a,
            lines_b,
            fromfile=f"v{version_a:03d}",
            tofile=f"v{version_b:03d}",
        )
    )
    diff_text = "".join(diff_lines)
    additions = sum(
        1 for line in diff_lines if line.startswith("+") and not line.startswith("+++")
    )
    deletions = sum(
        1 for line in diff_lines if line.startswith("-") and not line.startswith("---")
    )

    return VersionDiffResponse(
        version_a=version_a,
        version_b=version_b,
        diff_text=diff_text,
        additions=additions,
        deletions=deletions,
    )


@router.post("/{version_number}/restore", response_model=DocumentResponse)
async def api_restore_version(
    slug: str,
    doc_path: str,
    version_number: int,
    body: VersionRestoreRequest | None = None,
    branch: str = "main",
    session: AsyncSession = Depends(get_session),
):
    project_path = _get_project_path(slug)
    canonical_path = _normalize_document_path(doc_path)
    try:
        restored = restore_document_version(
            project_path,
            canonical_path,
            version_number,
            branch=branch,
            label=body.label if body else None,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Version {version_number} not found")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        project_db_id = await _get_project_db_id(slug, session)
        if project_db_id:
            version_info = get_current_version(project_path, canonical_path, branch=branch)
            if version_info is not None:
                file_bytes = (project_path / canonical_path).read_bytes()
                await sync_document_version_to_db(
                    session=session,
                    project_id=project_db_id,
                    version_info=version_info,
                    canonical_path=canonical_path,
                    title=restored.title,
                    doc_type=restored.doc_type,
                    status=restored.status,
                    tags=restored.tags,
                    change_source="restore",
                    content_hash=restored.content_hash,
                    byte_size=len(file_bytes),
                    filesystem_path=version_info.version_file,
                )
                await log_audit_event(
                    session,
                    "web",
                    "restore_document",
                    project_db_id,
                    canonical_path,
                    new_hash=restored.content_hash,
                )
                await session.commit()
    except Exception:
        await session.rollback()
        logger.debug("DB sync skipped for restore", exc_info=True)

    latest = get_document(project_path, canonical_path)
    if latest is None:
        raise HTTPException(status_code=404, detail=f"Document '{canonical_path}' not found")
    return DocumentResponse(**latest.__dict__)
