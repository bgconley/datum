"""
FastAPI middleware for qwen3-embedder.

Provides correlation ID injection, request timing, and structured logging.
"""

import time
import uuid
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from qwen3_embedder.logging.structured import (
    get_logger,
    log_request,
    set_correlation_id,
)

logger = get_logger(__name__)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware to inject correlation IDs into requests.

    If X-Correlation-ID header is present, uses that value.
    Otherwise, generates a new UUID.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Get or generate correlation ID
        correlation_id = request.headers.get("X-Correlation-ID")
        if not correlation_id:
            correlation_id = str(uuid.uuid4())[:8]

        # Set in context for logging
        set_correlation_id(correlation_id)

        # Process request
        response = await call_next(request)

        # Add correlation ID to response headers
        response.headers["X-Correlation-ID"] = correlation_id

        return response


class TimingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to track request timing.

    Adds X-Response-Time header and logs request duration.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.perf_counter()

        response = await call_next(request)

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        # Add timing header
        response.headers["X-Response-Time"] = f"{elapsed_ms:.2f}ms"

        # Log request (skip health checks to reduce noise)
        if not request.url.path.startswith("/health"):
            log_request(
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                elapsed_ms=elapsed_ms,
            )

        return response


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """
    Middleware for additional request validation.

    Validates content-type and request size limits.
    """

    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check content length for POST requests
        if request.method == "POST":
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > self.MAX_CONTENT_LENGTH:
                from fastapi.responses import JSONResponse

                return JSONResponse(
                    status_code=413,
                    content={
                        "error": "request_too_large",
                        "message": f"Request body exceeds maximum size of {self.MAX_CONTENT_LENGTH} bytes",
                    },
                )

        return await call_next(request)
