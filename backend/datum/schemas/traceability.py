"""Pydantic schemas for traceability and insight APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DocumentLinkResponse(BaseModel):
    id: str
    source_document_path: str
    target_document_path: str
    link_type: str
    anchor_text: str | None = None
    auto_detected: bool
    confidence: float | None = None
    created_at: datetime | None = None


class DocumentLinksListResponse(BaseModel):
    links: list[DocumentLinkResponse] = Field(default_factory=list)
    total: int


class EntityRelationshipResponse(BaseModel):
    id: str
    source_entity: str
    target_entity: str
    relationship_type: str
    extraction_method: str
    evidence_text: str | None = None
    confidence: float | None = None
    created_at: datetime | None = None


class EntityRelationshipsListResponse(BaseModel):
    relationships: list[EntityRelationshipResponse] = Field(default_factory=list)
    total: int


class InsightResponse(BaseModel):
    id: str
    insight_type: str
    severity: str
    status: str
    title: str
    explanation: str | None = None
    confidence: float | None = None
    evidence: dict[str, Any] | None = None
    created_at: datetime | None = None
    resolved_at: datetime | None = None


class InsightsListResponse(BaseModel):
    insights: list[InsightResponse] = Field(default_factory=list)
    total: int


class InsightStatusUpdate(BaseModel):
    status: str


class AnalyzeResponse(BaseModel):
    contradictions_found: int
    staleness_found: int
    insights_created: int
    insights_skipped: int


class TraceabilityNodeResponse(BaseModel):
    uid: str | None = None
    title: str | None = None
    status: str | None = None
    description: str | None = None
    priority: str | None = None
    decision: str | None = None
    name: str | None = None
    entity_type: str | None = None


class TraceabilityChainResponse(BaseModel):
    requirement: TraceabilityNodeResponse | None = None
    decisions: list[TraceabilityNodeResponse] = Field(default_factory=list)
    schema_entities: list[TraceabilityNodeResponse] = Field(default_factory=list)
