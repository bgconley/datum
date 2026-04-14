from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

EMBEDDING_SCHEMA_DIMENSIONS = 1024


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://datum:datum_dev@localhost:5432/datum"
    projects_root: Path = Path("/tank/datum/projects")
    blobs_root: Path = Path("/tank/datum/blobs")
    cache_root: Path = Path("/tank/datum/cache")
    frontend_port: int = 3000
    api_port: int = 8001
    embedding_endpoint: str = "http://localhost:8010"
    embedding_model: str = "Qwen3-Embedding-4B"
    embedding_dimensions: int = EMBEDDING_SCHEMA_DIMENSIONS
    embedding_protocol: str = "qwen3_embedder"
    embedding_batch_size: int = 64
    embedding_query_instruction: str = (
        "Given a technical query about an internal software project, retrieve the most "
        "relevant passages from documentation, code-adjacent text, API descriptions, "
        "configuration notes, migration records, and operational runbooks that directly "
        "answer the query."
    )
    reranker_endpoint: str = "http://localhost:8011"
    reranker_model: str = "Qwen3-Reranker-0.6B"
    reranker_protocol: str = "qwen3_reranker"
    reranker_instruction: str = (
        "Given a technical query about an internal software project, judge whether the "
        "passage is a strong answer source. Prefer passages that are authoritative, "
        "specific, version-relevant, and operationally actionable. Favor exact API names, "
        "config keys, file paths, schema or migration details, and direct evidence over "
        "general discussion."
    )
    ner_endpoint: str = "http://localhost:8012"
    ner_model: str = "knowledgator/gliner-bi-large-v2.0"
    ner_protocol: str = "gliner_http"
    ner_threshold: float = 0.5
    llm_endpoint: str = "http://localhost:8000"
    llm_model: str = "gpt-oss-20b"
    llm_max_tokens: int = 2048
    llm_temperature: float = 0.1
    blobs_quarantine_root: Path = Path("/tank/datum/blobs-quarantine")
    max_upload_bytes: int = 50 * 1024 * 1024
    api_rate_limit_requests: int = 120
    api_rate_limit_window_seconds: int = 60
    search_result_limit: int = Field(default=100, ge=1, le=1000)
    worker_poll_interval: float = Field(default=2.0, gt=0)

    # For local dev/testing, override paths
    model_config = {"env_prefix": "DATUM_"}

    @field_validator("embedding_dimensions")
    @classmethod
    def validate_embedding_dimensions(cls, value: int) -> int:
        if value != EMBEDDING_SCHEMA_DIMENSIONS:
            raise ValueError(
                "DATUM_EMBEDDING_DIMENSIONS must match the schema dimension "
                f"({EMBEDDING_SCHEMA_DIMENSIONS})."
            )
        return value


settings = Settings()


def get_settings() -> Settings:
    return settings
