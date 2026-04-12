from pydantic import BaseModel


class SearchRequest(BaseModel):
    query: str
    project: str | None = None
    version_scope: str = "current"
    limit: int = 20


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


class SearchResponse(BaseModel):
    results: list[SearchResultResponse]
    query: str
    result_count: int
    latency_ms: int | None = None
