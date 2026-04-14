from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from datum.db import get_session
from datum.models.core import Document, Project
from datum.models.operational import Collection, CollectionMember
from datum.schemas.collection import (
    CollectionCreate,
    CollectionMemberAdd,
    CollectionMemberResponse,
    CollectionResponse,
)

router = APIRouter(prefix="/api/v1/projects/{slug}/collections", tags=["collections"])


async def _get_project(slug: str, session: AsyncSession) -> Project:
    result = await session.execute(select(Project).where(Project.slug == slug))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")
    return project


async def _get_collection(slug: str, collection_id: str, session: AsyncSession) -> Collection:
    project = await _get_project(slug, session)
    collection = await session.get(Collection, collection_id)
    if collection is None or collection.project_id != project.id:
        raise HTTPException(status_code=404, detail="Collection not found")
    return collection


@router.post("", response_model=CollectionResponse, status_code=201)
async def api_create_collection(
    slug: str,
    body: CollectionCreate,
    session: AsyncSession = Depends(get_session),
):
    project = await _get_project(slug, session)
    collection = Collection(project_id=project.id, name=body.name, description=body.description)
    session.add(collection)
    await session.flush()
    await session.commit()
    return CollectionResponse(
        id=str(collection.id),
        name=collection.name,
        description=collection.description,
        created_at=collection.created_at,
        member_count=0,
    )


@router.get("", response_model=list[CollectionResponse])
async def api_list_collections(
    slug: str,
    session: AsyncSession = Depends(get_session),
):
    project = await _get_project(slug, session)
    result = await session.execute(
        select(
            Collection.id,
            Collection.name,
            Collection.description,
            Collection.created_at,
            func.count(CollectionMember.document_id),
        )
        .outerjoin(CollectionMember, CollectionMember.collection_id == Collection.id)
        .where(Collection.project_id == project.id)
        .group_by(Collection.id)
        .order_by(Collection.created_at.desc())
    )
    return [
        CollectionResponse(
            id=str(row[0]),
            name=row[1],
            description=row[2],
            created_at=row[3],
            member_count=int(row[4] or 0),
        )
        for row in result.fetchall()
    ]


@router.delete("/{collection_id}")
async def api_delete_collection(
    slug: str,
    collection_id: str,
    session: AsyncSession = Depends(get_session),
):
    collection = await _get_collection(slug, collection_id, session)
    await session.delete(collection)
    await session.commit()
    return {"status": "deleted"}


@router.post("/{collection_id}/members", status_code=201)
async def api_add_collection_member(
    slug: str,
    collection_id: str,
    body: CollectionMemberAdd,
    session: AsyncSession = Depends(get_session),
):
    collection = await _get_collection(slug, collection_id, session)
    project = await _get_project(slug, session)
    document_result = await session.execute(
        select(Document).where(
            Document.project_id == project.id,
            Document.uid == body.document_uid,
        )
    )
    document = document_result.scalar_one_or_none()
    if document is None or document.project_id != project.id:
        raise HTTPException(status_code=404, detail="Document not found")

    existing = await session.get(
        CollectionMember,
        {"collection_id": collection.id, "document_id": document.id},
    )
    if existing is None:
        session.add(CollectionMember(collection_id=collection.id, document_id=document.id))
        await session.commit()
    return {"status": "added"}


@router.get("/{collection_id}/members", response_model=list[CollectionMemberResponse])
async def api_list_collection_members(
    slug: str,
    collection_id: str,
    session: AsyncSession = Depends(get_session),
):
    collection = await _get_collection(slug, collection_id, session)
    result = await session.execute(
        select(
            Document.uid,
            Document.title,
            Document.canonical_path,
            CollectionMember.added_at,
        )
        .join(CollectionMember, CollectionMember.document_id == Document.id)
        .where(CollectionMember.collection_id == collection.id)
        .order_by(CollectionMember.added_at.desc())
    )
    return [
        CollectionMemberResponse(
            document_uid=row[0],
            document_title=row[1],
            canonical_path=row[2],
            added_at=row[3],
        )
        for row in result.fetchall()
    ]


@router.get("/by-document/{document_uid}", response_model=list[CollectionResponse])
async def api_list_document_collections(
    slug: str,
    document_uid: str,
    session: AsyncSession = Depends(get_session),
):
    project = await _get_project(slug, session)
    document_result = await session.execute(
        select(Document).where(
            Document.project_id == project.id,
            Document.uid == document_uid,
        )
    )
    document = document_result.scalar_one_or_none()
    if document is None:
        return []

    member_counter = aliased(CollectionMember)
    member_count = (
        select(func.count(member_counter.document_id))
        .where(member_counter.collection_id == Collection.id)
        .correlate(Collection)
        .scalar_subquery()
    )
    result = await session.execute(
        select(
            Collection.id,
            Collection.name,
            Collection.description,
            Collection.created_at,
            member_count,
        )
        .join(CollectionMember, CollectionMember.collection_id == Collection.id)
        .where(
            Collection.project_id == project.id,
            CollectionMember.document_id == document.id,
        )
        .order_by(Collection.created_at.desc())
    )
    return [
        CollectionResponse(
            id=str(row[0]),
            name=row[1],
            description=row[2],
            created_at=row[3],
            member_count=int(row[4] or 0),
        )
        for row in result.fetchall()
    ]


@router.delete("/{collection_id}/members/{document_uid}")
async def api_remove_collection_member(
    slug: str,
    collection_id: str,
    document_uid: str,
    session: AsyncSession = Depends(get_session),
):
    collection = await _get_collection(slug, collection_id, session)
    document_result = await session.execute(
        select(Document).where(
            Document.project_id == collection.project_id,
            Document.uid == document_uid,
        )
    )
    document = document_result.scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Collection member not found")
    member = await session.get(
        CollectionMember,
        {"collection_id": collection.id, "document_id": document.id},
    )
    if member is None:
        raise HTTPException(status_code=404, detail="Collection member not found")
    await session.delete(member)
    await session.commit()
    return {"status": "removed"}
