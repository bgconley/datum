from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from gliner_ner_service import __version__
from gliner_ner_service.backend import GlinerBackend
from gliner_ner_service.config import Settings, get_settings
from gliner_ner_service.models import ExtractedEntity, ExtractRequest, HealthResponse


def create_app(
    *,
    settings: Settings | None = None,
    backend: GlinerBackend | None = None,
) -> FastAPI:
    config = settings or get_settings()
    runtime_backend = backend or GlinerBackend(model_id=config.model_id, device=config.device)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        app.state.settings = config
        app.state.backend = runtime_backend
        if backend is None:
            runtime_backend.load()
        yield

    app = FastAPI(
        title="Datum GLiNER NER Service",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.settings = config
    app.state.backend = runtime_backend

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        state_backend: GlinerBackend = app.state.backend
        state_settings: Settings = app.state.settings
        return HealthResponse(
            status="ok",
            model_id=state_settings.model_id,
            loaded=state_backend.loaded,
            device=state_settings.device,
        )

    @app.post("/extract", response_model=list[ExtractedEntity])
    async def extract(body: ExtractRequest) -> list[ExtractedEntity]:
        state_backend: GlinerBackend = app.state.backend
        state_settings: Settings = app.state.settings
        extracted = state_backend.extract(
            body.text,
            labels=body.labels,
            threshold=(
                body.threshold
                if body.threshold is not None
                else state_settings.default_threshold
            ),
        )
        return [ExtractedEntity(**item) for item in extracted]

    return app


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        create_app(),
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
