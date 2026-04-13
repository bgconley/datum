"""
Pydantic models for OpenAI-compatible embedding API.

Implements the OpenAI Embeddings API specification with
Qwen3-specific extensions (instruction, MRL dimensions).
"""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class EncodingFormat(str, Enum):
    """Embedding encoding format."""

    FLOAT = "float"
    BASE64 = "base64"


class InputType(str, Enum):
    """Semantic type of the embedding input."""

    DOCUMENT = "document"
    QUERY = "query"


class EmbeddingRequest(BaseModel):
    """
    OpenAI-compatible embedding request.

    Example:
        {
            "input": ["Hello world", "Machine learning"],
            "model": "qwen3-4b",
            "encoding_format": "float",
            "dimensions": null
        }
    """

    input: str | list[str] = Field(
        ...,
        description="Text(s) to embed. Can be a string or array of strings.",
        examples=[["Hello world", "Machine learning is amazing"]],
    )
    model: str = Field(
        default="Qwen/Qwen3-Embedding-4B",
        description="Model identifier (logged but service uses configured model)",
    )
    encoding_format: EncodingFormat = Field(
        default=EncodingFormat.FLOAT,
        description="Format for embedding values: float or base64",
    )
    dimensions: int | None = Field(
        default=None,
        description="Truncate embeddings to this dimension (MRL support, 32-2560)",
        ge=1,
        le=4096,
    )
    input_type: InputType = Field(
        default=InputType.DOCUMENT,
        description="Whether the input is a document body or a search query.",
    )
    # Qwen3 extension: instruction for query embedding
    instruction: str | None = Field(
        default=None,
        description="Custom instruction for query embedding (Qwen3 extension)",
    )

    def get_texts(self) -> list[str]:
        """Get input as a list of strings."""
        if isinstance(self.input, str):
            return [self.input]
        return self.input


class EmbeddingData(BaseModel):
    """Single embedding in response."""

    object: Literal["embedding"] = "embedding"
    embedding: list[float] | str = Field(
        ...,
        description="Embedding vector (float array) or base64-encoded",
    )
    index: int = Field(
        ...,
        description="Index of this embedding in the input array",
        ge=0,
    )


class EmbeddingUsage(BaseModel):
    """Token usage statistics."""

    prompt_tokens: int = Field(..., description="Number of tokens in the input", ge=0)
    total_tokens: int = Field(..., description="Total tokens processed", ge=0)


class EmbeddingResponse(BaseModel):
    """
    OpenAI-compatible embedding response.

    Example:
        {
            "object": "list",
            "data": [
                {"object": "embedding", "embedding": [0.1, 0.2, ...], "index": 0}
            ],
            "model": "Qwen/Qwen3-Embedding-4B",
            "usage": {"prompt_tokens": 10, "total_tokens": 10}
        }
    """

    object: Literal["list"] = "list"
    data: list[EmbeddingData]
    model: str
    usage: EmbeddingUsage


class ModelInfo(BaseModel):
    """Model information for /v1/models endpoint."""

    id: str
    object: Literal["model"] = "model"
    created: int
    owned_by: str = "qwen"


class ModelsResponse(BaseModel):
    """Response for /v1/models endpoint."""

    object: Literal["list"] = "list"
    data: list[ModelInfo]


class HealthResponse(BaseModel):
    """Basic health check response."""

    status: str = Field(..., description="Health status: ok, degraded, or error")
    backend: str | None = Field(None, description="Active backend name")
    model: str | None = Field(None, description="Loaded model ID")
    embedding_dimension: int | None = Field(None, description="Embedding dimension")


class ReadyResponse(BaseModel):
    """Detailed readiness check response."""

    ready: bool = Field(..., description="Whether service is ready to handle requests")
    backend: str = Field(..., description="Active backend name")
    device: str = Field(..., description="Compute device (cuda, mps, cpu)")
    model: str = Field(..., description="Loaded model ID")
    embedding_dimension: int = Field(..., description="Embedding dimension")
    warmup_completed: bool = Field(..., description="Whether warmup has completed")


class ErrorResponse(BaseModel):
    """Error response format."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    detail: str | None = Field(None, description="Additional error details")


class ConfigResponse(BaseModel):
    """Configuration information response."""

    profile: str = Field(..., description="Active profile name")
    backend: str = Field(..., description="Active backend name")
    model_id: str = Field(..., description="Model ID")
    embedding_dimension: int = Field(..., description="Embedding dimension")
    max_length: int = Field(..., description="Maximum sequence length")
    batch_size: int = Field(..., description="Batch size")
    default_instruction: str = Field(..., description="Default instruction for queries")
