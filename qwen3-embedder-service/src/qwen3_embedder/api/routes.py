"""
FastAPI routes for qwen3-embedder.

Implements OpenAI-compatible embedding API endpoints.
"""

import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from qwen3_embedder.api.models import (
    ConfigResponse,
    EmbeddingData,
    EmbeddingRequest,
    EmbeddingResponse,
    EmbeddingUsage,
    EncodingFormat,
    ErrorResponse,
    HealthResponse,
    InputType,
    ModelInfo,
    ModelsResponse,
    ReadyResponse,
)
from qwen3_embedder.core.embedding import (
    batch_truncate_embeddings,
    embedding_to_base64,
    validate_embedding_quality,
)
from qwen3_embedder.core.prompt import format_query
from qwen3_embedder.core.tokenization import EmbedderTokenizer
from qwen3_embedder.logging.structured import get_logger, log_embedding_request

logger = get_logger(__name__)

# Router for embedding endpoints
router = APIRouter()


@router.post(
    "/v1/embeddings",
    response_model=EmbeddingResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        503: {"model": ErrorResponse, "description": "Service not ready"},
    },
    summary="Create embeddings",
    description="Creates embedding vectors for the provided input texts.",
)
async def create_embeddings(
    request: EmbeddingRequest,
    http_request: Request,
) -> EmbeddingResponse:
    """
    Create embeddings for input texts.

    OpenAI-compatible endpoint that supports:
    - Single text or list of texts
    - Float or base64 encoding
    - MRL dimension truncation
    - Custom instruction for query embedding
    """
    # Get app state
    state = http_request.app.state
    backend = state.backend
    tokenizer_wrapper: EmbedderTokenizer = state.tokenizer
    profile = state.profile

    # Check if ready
    if not backend.is_loaded:
        raise HTTPException(
            status_code=503,
            detail={"error": "service_not_ready", "message": "Model not loaded yet"},
        )

    start_time = time.perf_counter()

    # Get texts and apply instruction formatting if needed
    texts = request.get_texts()

    # Validate request
    if len(texts) == 0:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_request", "message": "Input cannot be empty"},
        )

    if len(texts) > profile.limits.max_texts_per_request:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_request",
                "message": f"Too many texts. Maximum is {profile.limits.max_texts_per_request}",
            },
        )

    # Check for excessively long texts
    for i, text in enumerate(texts):
        if len(text) > profile.limits.max_text_chars:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "invalid_request",
                    "message": f"Text at index {i} exceeds maximum length of {profile.limits.max_text_chars} characters",
                },
            )

    # Query inputs get instruction prefixing; document inputs are embedded as-is.
    if request.input_type == InputType.QUERY or request.instruction:
        effective_instruction = request.instruction or profile.prompt.default_instruction
        formatted_texts = [
            format_query(t, effective_instruction) for t in texts
        ]
    else:
        formatted_texts = texts

    # Tokenize
    encoded, token_stats = tokenizer_wrapper.tokenize_with_stats(
        formatted_texts,
        max_length=profile.limits.max_length,
    )

    # Get embeddings
    embeddings = backend.forward(encoded["input_ids"], encoded["attention_mask"])

    # Validate embedding quality (in debug mode)
    quality = validate_embedding_quality(embeddings)
    if quality["has_nan"] or quality["has_inf"]:
        logger.error("embedding_quality_error", **quality)
        raise HTTPException(
            status_code=500,
            detail={"error": "embedding_error", "message": "Invalid embedding values detected"},
        )

    # Apply MRL dimension truncation if requested
    target_dim = request.dimensions
    if target_dim and target_dim < embeddings.shape[1]:
        embeddings = batch_truncate_embeddings(embeddings, target_dim)
        embedding_dim = target_dim
    else:
        embedding_dim = embeddings.shape[1]

    # Format embeddings based on encoding format
    embedding_data = []
    for i, emb in enumerate(embeddings):
        if request.encoding_format == EncodingFormat.BASE64:
            embedding_value: Any = embedding_to_base64(emb)
        else:
            embedding_value = emb.tolist()

        embedding_data.append(
            EmbeddingData(
                object="embedding",
                embedding=embedding_value,
                index=i,
            )
        )

    # Calculate elapsed time
    elapsed_ms = (time.perf_counter() - start_time) * 1000

    # Log request
    log_embedding_request(
        num_texts=len(texts),
        total_tokens=token_stats["total_tokens"],
        embedding_dim=embedding_dim,
        elapsed_ms=elapsed_ms,
        truncated_count=token_stats["truncated_count"],
        requested_model=request.model,
    )

    # Build response
    return EmbeddingResponse(
        object="list",
        data=embedding_data,
        model=profile.model_id,
        usage=EmbeddingUsage(
            prompt_tokens=token_stats["total_tokens"],
            total_tokens=token_stats["total_tokens"],
        ),
    )


@router.get(
    "/v1/models",
    response_model=ModelsResponse,
    summary="List models",
    description="Lists the available models.",
)
async def list_models(http_request: Request) -> ModelsResponse:
    """List available models."""
    profile = http_request.app.state.profile

    return ModelsResponse(
        object="list",
        data=[
            ModelInfo(
                id=profile.model_id,
                object="model",
                created=0,
                owned_by="qwen",
            )
        ],
    )


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Basic health check endpoint.",
)
async def health_check(http_request: Request) -> HealthResponse:
    """Basic health check."""
    state = http_request.app.state

    if hasattr(state, "backend") and state.backend is not None:
        backend = state.backend
        return HealthResponse(
            status="ok" if backend.is_loaded else "loading",
            backend=backend.backend_name,
            model=state.profile.model_id if hasattr(state, "profile") else None,
            embedding_dimension=backend.embedding_dimension() if backend.is_loaded else None,
        )

    return HealthResponse(status="starting")


@router.get(
    "/healthz",
    response_model=HealthResponse,
    summary="Detailed health check",
    description="Detailed health check with backend information.",
)
async def health_check_detailed(http_request: Request) -> HealthResponse:
    """Detailed health check with backend info."""
    return await health_check(http_request)


@router.get(
    "/ready",
    response_model=ReadyResponse,
    responses={503: {"model": ErrorResponse, "description": "Service not ready"}},
    summary="Readiness check",
    description="Check if service is ready to handle requests.",
)
async def readiness_check(http_request: Request) -> ReadyResponse:
    """Readiness check - returns 503 if not ready."""
    state = http_request.app.state

    if not hasattr(state, "backend") or state.backend is None:
        raise HTTPException(
            status_code=503,
            detail={"error": "not_ready", "message": "Backend not initialized"},
        )

    backend = state.backend
    if not backend.is_loaded:
        raise HTTPException(
            status_code=503,
            detail={"error": "not_ready", "message": "Model not loaded"},
        )

    device_info = backend.device_info()

    return ReadyResponse(
        ready=True,
        backend=backend.backend_name,
        device=device_info.get("device", "unknown"),
        model=state.profile.model_id,
        embedding_dimension=backend.embedding_dimension(),
        warmup_completed=getattr(state, "warmup_completed", False),
    )


@router.get(
    "/v1/config",
    response_model=ConfigResponse,
    summary="Get configuration",
    description="Get current service configuration.",
)
async def get_config(http_request: Request) -> ConfigResponse:
    """Get current configuration."""
    state = http_request.app.state
    profile = state.profile
    backend = state.backend

    return ConfigResponse(
        profile=state.config.settings.profile,
        backend=backend.backend_name,
        model_id=profile.model_id,
        embedding_dimension=backend.embedding_dimension(),
        max_length=profile.limits.max_length,
        batch_size=profile.batching.batch_size,
        default_instruction=profile.prompt.default_instruction,
    )
