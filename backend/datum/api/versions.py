import difflib
from pathlib import Path

from fastapi import APIRouter, HTTPException

from datum.config import settings
from datum.schemas.version import (
    VersionContentResponse,
    VersionDiffResponse,
    VersionResponse,
)
from datum.services.document_manager import _validate_document_path
from datum.services.filesystem import compute_content_hash
from datum.services.project_manager import get_project
from datum.services.versioning import list_versions, read_version_content

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


@router.get("", response_model=list[VersionResponse])
async def api_list_versions(slug: str, doc_path: str, branch: str = "main"):
    project_path = _get_project_path(slug)
    canonical_path = _normalize_document_path(doc_path)
    versions = list_versions(project_path, canonical_path, branch=branch)
    if not versions:
        raise HTTPException(
            status_code=404,
            detail=f"No versions found for '{canonical_path}'",
        )

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
