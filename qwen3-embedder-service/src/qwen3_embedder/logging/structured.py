"""
Structured logging configuration for qwen3-embedder.

Provides JSON-formatted logging with correlation IDs, timing metrics,
and consistent field naming for production observability.
"""

import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Any

import structlog

# Context variable for correlation ID
correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def get_correlation_id() -> str:
    """Get current correlation ID or generate a new one."""
    cid = correlation_id_var.get()
    if cid is None:
        cid = str(uuid.uuid4())[:8]
        correlation_id_var.set(cid)
    return cid


def set_correlation_id(cid: str) -> None:
    """Set correlation ID for current context."""
    correlation_id_var.set(cid)


def add_correlation_id(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Add correlation ID to log event."""
    event_dict["correlation_id"] = get_correlation_id()
    return event_dict


def add_service_info(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Add service identification to log event."""
    event_dict["service"] = "qwen3-embedder"
    return event_dict


def configure_logging(
    level: str = "INFO",
    log_format: str = "json",
    include_timestamp: bool = True,
) -> None:
    """
    Configure structured logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        log_format: Output format ("json" or "console")
        include_timestamp: Whether to include timestamp in logs
    """
    # Convert level string to logging level
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Configure processors
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        add_correlation_id,
        add_service_info,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if include_timestamp:
        processors.insert(0, structlog.processors.TimeStamper(fmt="iso"))

    # Add appropriate renderer based on format
    if log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Also configure standard library logging to use structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Configure uvicorn and other library loggers
    for logger_name in ["uvicorn", "uvicorn.access", "uvicorn.error", "httpx"]:
        logging.getLogger(logger_name).setLevel(log_level)


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """
    Get a structlog logger instance.

    Args:
        name: Logger name (optional)

    Returns:
        Bound structlog logger
    """
    return structlog.get_logger(name)


class LogContext:
    """
    Context manager for adding temporary context to logs.

    Usage:
        with LogContext(request_id="abc123", user_id="user1"):
            logger.info("Processing request")
    """

    def __init__(self, **kwargs: Any):
        self.context = kwargs
        self._tokens: list[Any] = []

    def __enter__(self) -> "LogContext":
        for key, value in self.context.items():
            token = structlog.contextvars.bind_contextvars(**{key: value})
            self._tokens.append((key, token))
        return self

    def __exit__(self, *args: Any) -> None:
        for key, _ in self._tokens:
            structlog.contextvars.unbind_contextvars(key)


def log_request(
    method: str,
    path: str,
    status_code: int,
    elapsed_ms: float,
    **extra: Any,
) -> None:
    """
    Log an HTTP request with standard fields.

    Args:
        method: HTTP method
        path: Request path
        status_code: Response status code
        elapsed_ms: Request duration in milliseconds
        **extra: Additional fields to log
    """
    logger = get_logger("http")
    logger.info(
        "request",
        method=method,
        path=path,
        status_code=status_code,
        elapsed_ms=round(elapsed_ms, 2),
        **extra,
    )


def log_embedding_request(
    num_texts: int,
    total_tokens: int,
    embedding_dim: int,
    elapsed_ms: float,
    truncated_count: int = 0,
    **extra: Any,
) -> None:
    """
    Log an embedding request with domain-specific fields.

    Args:
        num_texts: Number of texts embedded
        total_tokens: Total tokens processed
        embedding_dim: Embedding dimension
        elapsed_ms: Processing time in milliseconds
        truncated_count: Number of texts that were truncated
        **extra: Additional fields to log
    """
    logger = get_logger("embedding")
    logger.info(
        "embedding_complete",
        num_texts=num_texts,
        total_tokens=total_tokens,
        embedding_dim=embedding_dim,
        elapsed_ms=round(elapsed_ms, 2),
        truncated_count=truncated_count,
        throughput_texts_per_sec=round(num_texts / (elapsed_ms / 1000), 2) if elapsed_ms > 0 else 0,
        **extra,
    )
