from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    host: str = "127.0.0.1"
    port: int = 8012
    model_id: str = "knowledgator/gliner-bi-large-v2.0"
    device: str | None = None
    default_threshold: float = 0.5
    log_level: str = "info"

    model_config = {"env_prefix": "DATUM_GLINER_"}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
