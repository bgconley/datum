from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://datum:datum@localhost:5432/datum"
    projects_root: Path = Path("/tank/datum/projects")
    blobs_root: Path = Path("/tank/datum/blobs")
    cache_root: Path = Path("/tank/datum/cache")
    frontend_port: int = 3000
    api_port: int = 8001

    # For local dev/testing, override paths
    model_config = {"env_prefix": "DATUM_"}


settings = Settings()
