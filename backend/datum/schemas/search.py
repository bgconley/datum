from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    project: str | None = None
    version_scope: str = "current"
    limit: int = Field(default=20, ge=1, le=100)
    mode: Literal[
        "find_docs",
        "ask_question",
        "find_decisions",
        "search_history",
        "compare_over_time",
    ] = "find_docs"
    answer_mode: bool = False

    @field_validator("version_scope")
    @classmethod
    def validate_version_scope(cls, value: str) -> str:
        if value in {"current", "all"}:
            return value
        if value.startswith("as_of:"):
            raw_timestamp = value.split(":", 1)[1]
            try:
                parsed = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("version_scope as_of timestamp must be valid ISO-8601") from exc
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                raise ValueError("version_scope as_of timestamp must include a timezone")
            return f"as_of:{parsed.isoformat()}"
        if value.startswith("snapshot:"):
            snapshot_name = value.split(":", 1)[1].strip()
            if not snapshot_name:
                raise ValueError("version_scope snapshot name must be non-empty")
            return f"snapshot:{snapshot_name}"
        if value.startswith("branch:"):
            branch_name = value.split(":", 1)[1].strip()
            if not branch_name:
                raise ValueError("version_scope branch name must be non-empty")
            return f"branch:{branch_name}"
        raise ValueError(
            "version_scope must be current, all, as_of:<timestamp>, "
            "snapshot:<name>, or branch:<name>"
        )


class SearchResultResponse(BaseModel):
    document_title: str
    document_path: str
    document_type: str
    document_status: str
    project_slug: str
    heading_path: str
    snippet: str
    version_number: int
    content_hash: str
    fused_score: float
    matched_terms: list[str]
    document_uid: str = ""
    chunk_id: str = ""
    line_start: int = 0
    line_end: int = 0
    match_signals: list[str] = Field(default_factory=list)
    entities: list["SearchResultEntityResponse"] = Field(default_factory=list)


class SearchResultEntityResponse(BaseModel):
    canonical_name: str
    entity_type: str


class SourceRefResponse(BaseModel):
    project_slug: str
    document_uid: str
    version_number: int
    content_hash: str
    chunk_id: str
    canonical_path: str
    heading_path: list[str] = Field(default_factory=list)
    line_start: int = 0
    line_end: int = 0


class CitationResponse(BaseModel):
    index: int = 0
    human_readable: str = ""
    source_ref: SourceRefResponse


class AnswerModeResponse(BaseModel):
    answer: str = ""
    citations: list[CitationResponse] = Field(default_factory=list)
    error: str = ""
    model: str = ""


class SearchEntityFacetResponse(BaseModel):
    canonical_name: str
    entity_type: str
    count: int


class SearchResponse(BaseModel):
    results: list[SearchResultResponse]
    entity_facets: list[SearchEntityFacetResponse] = Field(default_factory=list)
    query: str
    result_count: int
    latency_ms: int | None = None
    answer: AnswerModeResponse | None = None


class SearchStreamEventResponse(BaseModel):
    event: Literal["phase", "error"]
    phase: Literal["lexical", "reranked", "answer_ready"] | None = None
    query: str
    results: list[SearchResultResponse] = Field(default_factory=list)
    entity_facets: list[SearchEntityFacetResponse] = Field(default_factory=list)
    result_count: int = 0
    latency_ms: int | None = None
    semantic_enabled: bool = False
    rerank_applied: bool = False
    answer: AnswerModeResponse | None = None
    message: str | None = None
