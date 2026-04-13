"""
Main entry point for qwen3-embedder service.

Initializes the FastAPI application, loads the model,
and starts the server.
"""

import signal
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from qwen3_embedder.api.middleware import (
    CorrelationIdMiddleware,
    RequestValidationMiddleware,
    TimingMiddleware,
)
from qwen3_embedder.api.routes import router
from qwen3_embedder.backends.registry import get_backend
from qwen3_embedder.core.config import AppConfig
from qwen3_embedder.core.tokenization import EmbedderTokenizer
from qwen3_embedder.logging.structured import configure_logging, get_logger
from qwen3_embedder.utils.warmup import run_warmup
from qwen3_embedder.version import __version__


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI lifespan handler for startup and shutdown.

    Handles:
    - Configuration loading
    - Model loading
    - Warmup passes
    - Graceful shutdown
    """
    logger = get_logger("startup")

    # Load configuration
    logger.info("loading_config")
    config = AppConfig.load()
    profile = config.get_profile()

    logger.info(
        "config_loaded",
        profile=config.settings.profile,
        backend=profile.backend,
        model_id=profile.model_id,
    )

    # Initialize backend
    logger.info("initializing_backend", backend=profile.backend)
    backend = get_backend(profile, config.settings.backend)

    logger.info(
        "backend_loaded",
        backend=backend.backend_name,
        device=backend.device_info().get("device"),
        embedding_dim=backend.embedding_dimension(),
    )

    # Create tokenizer wrapper
    tokenizer = EmbedderTokenizer(
        tokenizer=backend.get_tokenizer(),
        max_length=profile.limits.max_length,
    )

    # Store in app state
    app.state.config = config
    app.state.profile = profile
    app.state.backend = backend
    app.state.tokenizer = tokenizer
    app.state.warmup_completed = False

    # Run warmup
    logger.info("running_warmup")
    try:
        warmup_results = run_warmup(
            backend,
            batch_sizes=[1, profile.batching.batch_size],
        )
        app.state.warmup_completed = True
        logger.info("warmup_complete", **warmup_results)
    except Exception as e:
        logger.warning("warmup_failed", error=str(e))

    logger.info(
        "service_ready",
        version=__version__,
        port=config.settings.port,
        backend=backend.backend_name,
    )

    yield

    # Shutdown
    logger.info("shutting_down")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    # Load config for settings
    config = AppConfig.load()
    settings = config.settings

    # Configure logging
    configure_logging(
        level=settings.log_level,
        log_format=settings.log_format,
    )

    # Create FastAPI app
    app = FastAPI(
        title="Qwen3-Embedder",
        description="Multi-backend embedding service using Qwen3-Embedding models",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add custom middleware
    app.add_middleware(RequestValidationMiddleware)
    app.add_middleware(TimingMiddleware)
    app.add_middleware(CorrelationIdMiddleware)

    # Include routes
    app.include_router(router)

    return app


def main() -> None:
    """Main entry point."""
    # Load config
    config = AppConfig.load()
    settings = config.settings

    # Configure logging before anything else
    configure_logging(
        level=settings.log_level,
        log_format=settings.log_format,
    )

    logger = get_logger("main")
    logger.info(
        "starting_server",
        version=__version__,
        host=settings.host,
        port=settings.port,
        backend=settings.backend,
        profile=settings.profile,
    )

    # Handle signals for graceful shutdown
    def signal_handler(sig: int, frame: object) -> None:
        logger.info("received_signal", signal=sig)
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create app
    app = create_app()

    # Run server
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        access_log=False,  # We handle logging ourselves
    )


if __name__ == "__main__":
    main()
