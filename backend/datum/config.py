from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings

EMBEDDING_SCHEMA_DIMENSIONS = 1024


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://datum:datum@localhost:5432/datum"
    projects_root: Path = Path("/tank/datum/projects")
    blobs_root: Path = Path("/tank/datum/blobs")
    cache_root: Path = Path("/tank/datum/cache")
    frontend_port: int = 3000
    api_port: int = 8001
    embedding_endpoint: str = "http://localhost:8010"
    embedding_model: str = "Qwen3-Embedding-4B"
    embedding_dimensions: int = EMBEDDING_SCHEMA_DIMENSIONS
    embedding_protocol: str = "openai"
    embedding_batch_size: int = 64
    reranker_endpoint: str = "http://localhost:8011"
    reranker_model: str = "Qwen3-Reranker-0.6B"
    reranker_protocol: str = "openai"

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
