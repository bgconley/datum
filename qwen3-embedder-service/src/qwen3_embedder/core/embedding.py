"""
Embedding utilities for qwen3-embedder.

Provides backend-agnostic functions for embedding normalization,
MRL (Matryoshka Representation Learning) dimension truncation,
and similarity computation.

Key difference from reranker scoring:
- Reranker: extracts yes/no logits -> softmax -> p(yes) score
- Embedder: extracts last_hidden_state -> last_token_pool -> L2 normalize
"""

import logging

import numpy as np

logger = logging.getLogger(__name__)


def l2_normalize(embeddings: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    """
    L2-normalize embeddings along the last dimension.

    Args:
        embeddings: Shape [batch, dim] or [dim]
        eps: Small constant to avoid division by zero

    Returns:
        Normalized embeddings with unit L2 norm
    """
    # Handle 1D case
    if embeddings.ndim == 1:
        embeddings = embeddings[np.newaxis, :]

    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    return embeddings / np.maximum(norms, eps)


def truncate_embedding(
    embedding: np.ndarray,
    target_dim: int | None = None,
    renormalize: bool = True,
) -> np.ndarray:
    """
    Truncate embedding to target dimension (Matryoshka Representation Learning).

    Qwen3 embeddings support MRL - you can use smaller dimensions (32-2560)
    while maintaining quality for the reduced dimension space.

    Args:
        embedding: Full embedding vector, shape [dim] or [batch, dim]
        target_dim: Desired dimension (must be <= original dim)
        renormalize: Whether to re-normalize after truncation

    Returns:
        Truncated (and optionally re-normalized) embedding
    """
    if target_dim is None or target_dim >= embedding.shape[-1]:
        return embedding

    # Validate target dimension
    if target_dim < 1:
        raise ValueError(f"target_dim must be >= 1, got {target_dim}")

    # Truncate
    truncated = embedding[..., :target_dim]

    # Re-normalize if requested
    if renormalize:
        truncated = l2_normalize(truncated)

    return truncated


def batch_truncate_embeddings(
    embeddings: np.ndarray,
    target_dim: int | None = None,
    renormalize: bool = True,
) -> np.ndarray:
    """
    Truncate a batch of embeddings to target dimension.

    Args:
        embeddings: Shape [batch, dim]
        target_dim: Desired dimension
        renormalize: Whether to re-normalize after truncation

    Returns:
        Truncated embeddings, shape [batch, target_dim]
    """
    if target_dim is None or target_dim >= embeddings.shape[-1]:
        return embeddings

    truncated = embeddings[:, :target_dim]

    if renormalize:
        truncated = l2_normalize(truncated)

    return truncated


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """
    Compute cosine similarity between embeddings.

    Assumes embeddings are already L2-normalized.

    Args:
        a: Shape [n, dim] or [dim]
        b: Shape [m, dim] or [dim]

    Returns:
        Similarity matrix of shape [n, m] or scalar
    """
    # Handle 1D case
    if a.ndim == 1:
        a = a[np.newaxis, :]
    if b.ndim == 1:
        b = b[np.newaxis, :]

    return a @ b.T


def dot_product_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """
    Compute dot product similarity between embeddings.

    For L2-normalized embeddings, this is equivalent to cosine similarity.

    Args:
        a: Shape [n, dim] or [dim]
        b: Shape [m, dim] or [dim]

    Returns:
        Similarity matrix of shape [n, m] or scalar
    """
    return cosine_similarity(a, b)


def euclidean_distance(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """
    Compute Euclidean distance between embeddings.

    Args:
        a: Shape [n, dim] or [dim]
        b: Shape [m, dim] or [dim]

    Returns:
        Distance matrix of shape [n, m] or scalar
    """
    # Handle 1D case
    if a.ndim == 1:
        a = a[np.newaxis, :]
    if b.ndim == 1:
        b = b[np.newaxis, :]

    # Compute squared distances efficiently
    # ||a - b||^2 = ||a||^2 + ||b||^2 - 2 * a . b
    a_sq = np.sum(a**2, axis=1, keepdims=True)
    b_sq = np.sum(b**2, axis=1, keepdims=True)
    distances_sq = a_sq + b_sq.T - 2 * (a @ b.T)

    # Clip to avoid negative values due to numerical errors
    distances_sq = np.maximum(distances_sq, 0)

    return np.sqrt(distances_sq)


def validate_embedding_quality(embeddings: np.ndarray) -> dict:
    """
    Validate embedding quality for debugging/monitoring.

    Checks for common issues like non-normalized vectors,
    NaN/Inf values, and unusual distributions.

    Args:
        embeddings: Shape [batch, dim]

    Returns:
        Dictionary with quality metrics
    """
    norms = np.linalg.norm(embeddings, axis=1)

    return {
        "batch_size": embeddings.shape[0],
        "dimension": embeddings.shape[1],
        "norm_min": float(np.min(norms)),
        "norm_max": float(np.max(norms)),
        "norm_mean": float(np.mean(norms)),
        "norm_std": float(np.std(norms)),
        "is_normalized": bool(np.allclose(norms, 1.0, atol=1e-5)),
        "has_nan": bool(np.any(np.isnan(embeddings))),
        "has_inf": bool(np.any(np.isinf(embeddings))),
        "value_min": float(np.min(embeddings)),
        "value_max": float(np.max(embeddings)),
        "value_mean": float(np.mean(embeddings)),
    }


def embedding_to_base64(embedding: np.ndarray) -> str:
    """
    Convert embedding to base64-encoded string.

    OpenAI API supports base64 encoding for embeddings.

    Args:
        embedding: Single embedding vector, shape [dim]

    Returns:
        Base64-encoded string
    """
    import base64

    # Ensure float32
    embedding = embedding.astype(np.float32)
    return base64.b64encode(embedding.tobytes()).decode("utf-8")


def base64_to_embedding(encoded: str, dim: int) -> np.ndarray:
    """
    Convert base64-encoded string to embedding.

    Args:
        encoded: Base64-encoded string
        dim: Expected embedding dimension

    Returns:
        Embedding vector, shape [dim]
    """
    import base64

    data = base64.b64decode(encoded)
    return np.frombuffer(data, dtype=np.float32).reshape(dim)


# MRL (Matryoshka) dimension presets
MRL_DIMENSIONS = {
    "tiny": 32,
    "small": 64,
    "medium": 128,
    "base": 256,
    "large": 512,
    "xlarge": 1024,
    "full_06b": 1024,  # Full dimension for 0.6B model
    "full_4b": 2560,  # Full dimension for 4B model
    "full_8b": 4096,  # Full dimension for 8B model
}


def get_mrl_dimension(name_or_int: str | int) -> int:
    """
    Get MRL dimension from name or integer.

    Args:
        name_or_int: Dimension name (e.g., "small", "medium") or integer

    Returns:
        Dimension as integer
    """
    if isinstance(name_or_int, int):
        return name_or_int

    name = name_or_int.lower()
    if name in MRL_DIMENSIONS:
        return MRL_DIMENSIONS[name]

    # Try parsing as integer
    try:
        return int(name)
    except ValueError as exc:
        available = list(MRL_DIMENSIONS.keys())
        raise ValueError(f"Unknown MRL dimension: {name}. Available: {available}") from exc
