from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    project: str | None = None
    version_scope: str = "current"
    limit: int = Field(default=20, ge=1, le=100)

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
        raise ValueError("version_scope must be current, all, or as_of:<timestamp>")


class SearchResultResponse(BaseModel):
    document_title: str
    document_path: str
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
    match_signals: list[str] = []


class SearchResponse(BaseModel):
    results: list[SearchResultResponse]
    query: str
    result_count: int
    latency_ms: int | None = None


class SearchStreamEventResponse(BaseModel):
    event: Literal["phase", "error"]
    phase: Literal["lexical", "reranked"] | None = None
    query: str
    results: list[SearchResultResponse] = []
    result_count: int = 0
    latency_ms: int | None = None
    semantic_enabled: bool = False
    rerank_applied: bool = False
    message: str | None = None
