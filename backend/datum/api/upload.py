from __future__ import annotations

import logging
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from datum.config import settings
from datum.db import get_session
from datum.models.core import Project
from datum.models.operational import Attachment
from datum.services.blob_store import store_blob
from datum.services.filesystem import atomic_write
from datum.services.project_manager import get_project

router = APIRouter(prefix="/api/v1/projects/{slug}/upload", tags=["upload"])
logger = logging.getLogger(__name__)


def _safe_attachment_stem(filename: str) -> str:
    stem = Path(filename).stem.lower()
    safe = "".join(ch if ch.isalnum() else "-" for ch in stem).strip("-")
    return safe or "attachment"


@router.post("", status_code=201)
async def api_upload_file(
    slug: str,
    file: UploadFile,
    session: AsyncSession = Depends(get_session),
):
    project_info = get_project(settings.projects_root, slug)
    if project_info is None:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty upload")
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="Upload exceeds max_upload_bytes")

    filename = file.filename or "upload.bin"
    extension = Path(filename).suffix
    blob = store_blob(content, extension, settings.blobs_root)

    content_hash_suffix = str(blob["content_hash"]).split(":", 1)[1][:8]
    attachment_name = f"{_safe_attachment_stem(filename)}-{content_hash_suffix}"
    attachment_relative = f"attachments/{attachment_name}/metadata.yaml"
    attachment_dir = settings.projects_root / slug / "attachments" / attachment_name
    attachment_dir.mkdir(parents=True, exist_ok=True)
    metadata_payload = {
        "filename": filename,
        "content_type": file.content_type or "application/octet-stream",
        "size_bytes": int(blob["size_bytes"]),
        "blob_ref": blob["content_hash"],
        "blob_path": blob["blob_path"],
    }
    atomic_write(
        attachment_dir / "metadata.yaml",
        yaml.safe_dump(metadata_payload, sort_keys=False).encode("utf-8"),
    )

    try:
        project_result = await session.execute(select(Project).where(Project.slug == slug))
        project = project_result.scalar_one_or_none()
        if project is not None:
            attachment = Attachment(
                project_id=project.id,
                filename=filename,
                content_type=file.content_type or "application/octet-stream",
                byte_size=int(blob["size_bytes"]),
                content_hash=str(blob["content_hash"]),
                blob_path=str(blob["blob_path"]),
                filesystem_path=attachment_relative,
                metadata_=metadata_payload,
            )
            session.add(attachment)
            await session.commit()
    except Exception as exc:
        await session.rollback()
        logger.warning(
            "DB sync skipped for upload (project=%s, attachment_path=%s): %s",
            slug,
            attachment_relative,
            exc,
            exc_info=True,
        )

    return {
        "filename": filename,
        "attachment_path": attachment_relative,
        "content_hash": blob["content_hash"],
        "blob_path": blob["blob_path"],
        "size_bytes": blob["size_bytes"],
    }
