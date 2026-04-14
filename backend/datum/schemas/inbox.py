from __future__ import annotations

from pydantic import BaseModel, Field


class CandidateResponse(BaseModel):
    id: str
    candidate_type: str
    title: str
    context: str | None = None
    severity: str
    decision: str | None = None
    consequences: str | None = None
    description: str | None = None
    priority: str | None = None
    resolution: str | None = None
    curation_status: str
    extraction_method: str | None = None
    confidence: float | None = None
    source_doc_path: str | None = None
    source_version: int | None = None
    created_at: str | None = None


class AcceptCandidateRequest(BaseModel):
    title: str | None = None
    context: str | None = None
    decision: str | None = None
    consequences: str | None = None
    description: str | None = None
    priority: str | None = None
    resolution: str | None = None


class CandidateActionResponse(BaseModel):
    id: str
    curation_status: str
    canonical_record_path: str | None = None


class EntitySummaryResponse(BaseModel):
    entity_type: str
    canonical_name: str
    count: int


class OpenQuestionSummaryResponse(BaseModel):
    id: str
    question: str
    context: str | None = None
    age_days: int
    is_stale: bool
    source_doc_path: str | None = None
    source_version: int | None = None
    canonical_record_path: str | None = None
    created_at: str | None = None


class ProjectIntelligenceSummaryResponse(BaseModel):
    pending_candidate_count: int = 0
    key_entities: list[EntitySummaryResponse] = Field(default_factory=list)
    open_questions: list[OpenQuestionSummaryResponse] = Field(default_factory=list)
