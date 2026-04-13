from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


def _validate_version_scope(value: str) -> str:
    if value in {"current", "all"}:
        return value
    if value.startswith("as_of:"):
        raw_timestamp = value.split(":", 1)[1]
        parsed = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("version_scope as_of timestamp must include a timezone")
        return f"as_of:{parsed.isoformat()}"
    raise ValueError("version_scope must be current, all, or as_of:<timestamp>")


class EvalSetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    queries: list[dict]


class EvalSetResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    query_count: int
    created_at: str | None = None


class EvalRunRequest(BaseModel):
    eval_set_id: str
    name: str = Field(min_length=1, max_length=200)
    retrieval_config_id: str | None = None
    embedding_model: str | None = None
    embedding_model_run_id: str | None = None
    reranker_model: str | None = None
    reranker_model_run_id: str | None = None
    reranker_enabled: bool = True
    version_scope: str = "current"

    @field_validator("version_scope")
    @classmethod
    def validate_version_scope(cls, value: str) -> str:
        return _validate_version_scope(value)


class EvalRunResponse(BaseModel):
    id: str
    name: str
    results: dict
    created_at: str | None = None


class CompareResponse(BaseModel):
    winner: str
    run_a: str
    run_b: str
    ndcg_at_5_a: float
    ndcg_at_5_b: float
    ndcg_at_5_delta: float
    recall_at_5_a: float
    recall_at_5_b: float
    mrr_a: float
    mrr_b: float
    latency_a_ms: float
    latency_b_ms: float
    latency_delta_ms: float


class EmbeddingStatsResponse(BaseModel):
    models: list[dict]
