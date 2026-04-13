"""
Qwen3-Embedder Multi-Backend Service

A high-performance embedding service using Qwen3-Embedding models
with support for PyTorch (CUDA/MPS/CPU), vLLM, and MLX backends.
"""

from qwen3_embedder.version import __version__

__all__ = ["__version__"]
