"""
MLX Backend - Tertiary implementation for Apple Silicon optimization.

This backend uses MLX for efficient inference on Apple Silicon Macs.
It leverages the unified memory architecture and uses quantized models
from mlx-community for optimal performance.

NOTE: MLX only works on Apple Silicon (M1/M2/M3) Macs.
"""

import logging
import platform
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class MLXBackend:
    """
    MLX backend for Apple Silicon Macs - TERTIARY BACKEND.

    Uses MLX with 4-bit quantized models from mlx-community
    for optimal performance on Apple Silicon.
    """

    # Model mapping for convenience
    MODEL_ALIASES = {
        "small": "mlx-community/Qwen3-Embedding-0.6B-4bit-DWQ",
        "medium": "mlx-community/Qwen3-Embedding-4B-4bit-DWQ",
        "large": "mlx-community/Qwen3-Embedding-8B-4bit-DWQ",
    }

    EMBEDDING_DIMS = {
        "0.6B": 1024,
        "4B": 2560,
        "8B": 4096,
    }

    def __init__(self):
        """Initialize MLX backend."""
        self._model = None
        self._tokenizer = None
        self._loaded = False
        self._embedding_dim: int | None = None
        self._model_id: str | None = None

    def load_model(self, model_id: str, **kwargs: Any) -> None:
        """
        Load MLX model and HuggingFace tokenizer.

        Args:
            model_id: MLX model path or alias (small/medium/large)
            **kwargs: Additional options:
                - hf_tokenizer_id: HuggingFace tokenizer ID (if different from model)
        """
        # Check platform
        if platform.machine() != "arm64" or platform.system() != "Darwin":
            raise RuntimeError("MLX backend only works on Apple Silicon Macs")

        try:
            from mlx_lm import load as mlx_load
            from transformers import AutoTokenizer
        except ImportError as e:
            raise ImportError(
                "MLX not installed. Install with: pip install mlx mlx-lm"
            ) from e

        # Resolve alias if provided
        if model_id in self.MODEL_ALIASES:
            model_id = self.MODEL_ALIASES[model_id]

        self._model_id = model_id
        logger.info(f"Loading MLX model: {model_id}")

        # Load MLX model
        self._model, self._mlx_tokenizer = mlx_load(model_id)

        # Load HuggingFace tokenizer for consistency with other backends
        hf_tokenizer_id = kwargs.get("hf_tokenizer_id", self._get_hf_tokenizer_id(model_id))
        logger.info(f"Loading HuggingFace tokenizer: {hf_tokenizer_id}")

        self._tokenizer = AutoTokenizer.from_pretrained(hf_tokenizer_id, padding_side="left")
        if self._tokenizer.pad_token is None:
            self._tokenizer.pad_token = self._tokenizer.eos_token

        # Determine embedding dimension
        self._embedding_dim = self._get_embedding_dim(model_id)

        self._loaded = True
        logger.info(f"MLX backend loaded successfully: embedding_dim={self._embedding_dim}")

    def _get_hf_tokenizer_id(self, model_id: str) -> str:
        """Map MLX model ID to HuggingFace tokenizer ID."""
        if "0.6B" in model_id:
            return "Qwen/Qwen3-Embedding-0.6B"
        elif "4B" in model_id:
            return "Qwen/Qwen3-Embedding-4B"
        elif "8B" in model_id:
            return "Qwen/Qwen3-Embedding-8B"
        return "Qwen/Qwen3-Embedding-4B"  # Default

    def _get_embedding_dim(self, model_id: str) -> int:
        """Get embedding dimension from model ID."""
        if "0.6B" in model_id:
            return 1024
        elif "4B" in model_id:
            return 2560
        elif "8B" in model_id:
            return 4096
        return 2560  # Default

    def get_tokenizer(self) -> Any:
        """Return the HuggingFace tokenizer."""
        if self._tokenizer is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")
        return self._tokenizer

    def forward(
        self,
        input_ids: np.ndarray,
        attention_mask: np.ndarray,
    ) -> np.ndarray:
        """
        Run forward pass and return L2-normalized embeddings.

        Args:
            input_ids: Token IDs, shape [batch, seq_len], dtype int64
            attention_mask: Attention mask, shape [batch, seq_len], dtype int64

        Returns:
            L2-normalized embeddings, shape [batch, embedding_dim], dtype float32
        """
        if not self._loaded:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        import mlx.core as mx

        # Convert to MLX array
        tokens = mx.array(input_ids)

        # Forward pass - get hidden states
        # Note: The exact API depends on the MLX model structure
        # This assumes the model returns hidden states directly
        hidden_states = self._model(tokens)

        # If hidden_states has shape [batch, seq, hidden], extract last token
        embeddings = hidden_states[:, -1, :] if len(hidden_states.shape) == 3 else hidden_states

        # L2 normalize
        norms = mx.sqrt(mx.sum(embeddings**2, axis=1, keepdims=True))
        embeddings = embeddings / mx.maximum(norms, mx.array(1e-12))

        # Ensure computation complete and convert to numpy
        mx.eval(embeddings)

        return np.array(embeddings, dtype=np.float32)

    def warmup(self, batch_size: int = 1, seq_len: int = 128) -> float:
        """Run warmup pass."""
        import time

        try:
            import mlx.core as mx
        except ImportError:
            return 0.0

        if not self._loaded:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        logger.info(f"Running MLX warmup (batch_size={batch_size}, seq_len={seq_len})")

        dummy_ids = np.ones((batch_size, seq_len), dtype=np.int64)
        dummy_mask = np.ones((batch_size, seq_len), dtype=np.int64)

        start = time.perf_counter()
        _ = self.forward(dummy_ids, dummy_mask)
        mx.synchronize()
        elapsed_ms = (time.perf_counter() - start) * 1000

        logger.info(f"MLX warmup complete: {elapsed_ms:.1f}ms")
        return elapsed_ms

    def embedding_dimension(self) -> int:
        """Return the embedding dimension."""
        if self._embedding_dim is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")
        return self._embedding_dim

    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        info: dict[str, Any] = {
            "backend": "mlx",
            "device": "apple_silicon",
            "device_name": platform.processor(),
            "embedding_dimension": self._embedding_dim,
            "model_id": self._model_id,
        }

        try:
            import mlx.core as mx

            info["default_device"] = str(mx.default_device())
        except ImportError:
            pass

        return info

    @property
    def is_loaded(self) -> bool:
        """Return True if model is loaded."""
        return self._loaded

    @property
    def backend_name(self) -> str:
        """Return backend identifier."""
        return "mlx"
