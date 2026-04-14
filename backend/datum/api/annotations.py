from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from datum.db import get_session
from datum.models.core import DocumentVersion
from datum.models.operational import Annotation
from datum.schemas.annotation import AnnotationCreate, AnnotationResponse

router = APIRouter(prefix="/api/v1/annotations", tags=["annotations"])

_VALID_TYPES = {"comment", "highlight", "pin"}


def _parse_uuid(raw_value: str, *, field_name: str) -> UUID:
    try:
        return UUID(raw_value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid {field_name}") from exc


@router.post("", response_model=AnnotationResponse, status_code=201)
async def api_create_annotation(
    body: AnnotationCreate,
    session: AsyncSession = Depends(get_session),
):
    if body.annotation_type not in _VALID_TYPES:
        raise HTTPException(status_code=422, detail="Invalid annotation type")

    version_uuid = _parse_uuid(body.version_id, field_name="version_id")
    version = await session.get(DocumentVersion, version_uuid)
    if version is None:
        raise HTTPException(status_code=404, detail="Document version not found")

    annotation = Annotation(
        version_id=version.id,
        annotation_type=body.annotation_type,
        content=body.content,
        start_char=body.start_char,
        end_char=body.end_char,
    )
    session.add(annotation)
    await session.flush()
    await session.commit()
    return AnnotationResponse(
        id=str(annotation.id),
        version_id=str(annotation.version_id),
        annotation_type=annotation.annotation_type,
        content=annotation.content,
        start_char=annotation.start_char,
        end_char=annotation.end_char,
        created_at=annotation.created_at,
    )


@router.get("", response_model=list[AnnotationResponse])
async def api_list_annotations(
    version_id: str = Query(...),
    session: AsyncSession = Depends(get_session),
):
    version_uuid = _parse_uuid(version_id, field_name="version_id")
    result = await session.execute(
        select(Annotation)
        .where(Annotation.version_id == version_uuid)
        .order_by(Annotation.start_char.asc().nullslast(), Annotation.created_at.desc())
    )
    items = result.scalars().all()
    return [
        AnnotationResponse(
            id=str(item.id),
            version_id=str(item.version_id),
            annotation_type=item.annotation_type,
            content=item.content,
            start_char=item.start_char,
            end_char=item.end_char,
            created_at=item.created_at,
        )
        for item in items
    ]


@router.delete("/{annotation_id}")
async def api_delete_annotation(
    annotation_id: str,
    session: AsyncSession = Depends(get_session),
):
    annotation_uuid = _parse_uuid(annotation_id, field_name="annotation_id")
    annotation = await session.get(Annotation, annotation_uuid)
    if annotation is None:
        raise HTTPException(status_code=404, detail="Annotation not found")
    await session.delete(annotation)
    await session.commit()
    return {"status": "deleted"}
