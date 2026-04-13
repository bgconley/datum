"""Custom exceptions for qwen3-embedder."""


class EmbedderError(Exception):
    """Base exception for all embedder errors."""

    pass


class ConfigurationError(EmbedderError):
    """Raised when configuration is invalid or missing."""

    pass


class EmbeddingError(EmbedderError):
    """Raised when embedding extraction fails."""

    pass


class BackendError(EmbedderError):
    """Raised when a backend operation fails."""

    pass


class TokenizationError(EmbedderError):
    """Raised when tokenization fails."""

    pass


class ModelLoadError(EmbedderError):
    """Raised when model loading fails."""

    pass


class ValidationError(EmbedderError):
    """Raised when request validation fails."""

    pass
