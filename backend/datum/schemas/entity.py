"""Pydantic schemas for entity APIs."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EntitySummaryResponse(BaseModel):
    id: str
    entity_type: str
    canonical_name: str
    mention_count: int


class EntityListResponse(BaseModel):
    entities: list[EntitySummaryResponse] = Field(default_factory=list)
    total: int


class EntityMentionDetailResponse(BaseModel):
    document_path: str
    document_title: str | None = None
    chunk_content_snippet: str
    start_char: int
    end_char: int
    confidence: float
    version_number: int | None = None


class EntityRelationshipDetailResponse(BaseModel):
    related_entity: str
    relationship_type: str
    direction: str
    evidence_text: str | None = None
    evidence_document_path: str | None = None
    evidence_document_title: str | None = None
    evidence_heading_path: str | None = None
    evidence_version_number: int | None = None
    evidence_chunk_id: str | None = None
    evidence_start_char: int | None = None
    evidence_end_char: int | None = None


class EntityDetailResponse(BaseModel):
    id: str
    entity_type: str
    canonical_name: str
    mentions: list[EntityMentionDetailResponse] = Field(default_factory=list)
    relationships: list[EntityRelationshipDetailResponse] = Field(default_factory=list)
    mention_count: int
