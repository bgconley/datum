from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CollectionCreate(BaseModel):
    name: str
    description: str | None = None


class CollectionResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    member_count: int = 0
    created_at: datetime | None = None


class CollectionMemberAdd(BaseModel):
    document_uid: str


class CollectionMemberResponse(BaseModel):
    document_uid: str
    document_title: str
    canonical_path: str
    added_at: datetime | None = None
