"""
vLLM Backend - Secondary implementation for high-throughput CUDA inference.

This backend uses vLLM for efficient batched inference on NVIDIA GPUs.
It supports continuous batching and tensor parallelism for maximum throughput.

NOTE: vLLM requires CUDA and does not support MPS or CPU.
"""

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class VLLMBackend:
    """
    vLLM backend for high-throughput CUDA inference - SECONDARY BACKEND.

    Uses vLLM's optimized inference engine with continuous batching.
    Requires CUDA-capable GPU.
    """

    def __init__(self):
        """Initialize vLLM backend."""
        self._model = None
        self._tokenizer = None
        self._loaded = False
        self._embedding_dim: int | None = None
        self._model_id: str | None = None

    def load_model(self, model_id: str, **kwargs: Any) -> None:
        """
        Load vLLM embedding model.

        Args:
            model_id: HuggingFace model ID (e.g., "Qwen/Qwen3-Embedding-4B")
            **kwargs: vLLM-specific options:
                - tensor_parallel_size: Number of GPUs for tensor parallelism
                - gpu_memory_utilization: Fraction of GPU memory to use
                - max_model_len: Maximum sequence length
                - trust_remote_code: Whether to trust remote code
        """
        try:
            from transformers import AutoConfig, AutoTokenizer
            from vllm import LLM
        except ImportError as e:
            raise ImportError(
                "vLLM not installed. Install with: pip install vllm"
            ) from e

        self._model_id = model_id

        # Get model config to determine embedding dimension
        config = AutoConfig.from_pretrained(model_id, trust_remote_code=True)
        self._embedding_dim = config.hidden_size

        # Load tokenizer with LEFT padding
        self._tokenizer = AutoTokenizer.from_pretrained(model_id, padding_side="left")
        if self._tokenizer.pad_token is None:
            self._tokenizer.pad_token = self._tokenizer.eos_token

        # vLLM options
        tensor_parallel_size = kwargs.get("tensor_parallel_size", 1)
        gpu_memory_utilization = kwargs.get("gpu_memory_utilization", 0.8)
        max_model_len = kwargs.get("max_model_len", 8192)
        trust_remote_code = kwargs.get("trust_remote_code", True)

        logger.info(
            f"Loading vLLM model: {model_id} "
            f"(tp_size={tensor_parallel_size}, gpu_util={gpu_memory_utilization})"
        )

        # Load model with vLLM
        # Note: vLLM uses task="embed" for embedding models
        self._model = LLM(
            model=model_id,
            task="embed",
            tensor_parallel_size=tensor_parallel_size,
            gpu_memory_utilization=gpu_memory_utilization,
            max_model_len=max_model_len,
            trust_remote_code=trust_remote_code,
        )

        self._loaded = True
        logger.info(
            f"vLLM backend loaded successfully: embedding_dim={self._embedding_dim}"
        )

    def get_tokenizer(self) -> Any:
        """Return the tokenizer."""
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

        from vllm import TokensPrompt

        # Convert input_ids to list of TokensPrompt
        prompts = []
        for i in range(input_ids.shape[0]):
            # Get actual tokens (non-padding)
            mask = attention_mask[i]
            tokens = input_ids[i][mask == 1].tolist()
            prompts.append(TokensPrompt(prompt_token_ids=tokens))

        # Run inference
        outputs = self._model.embed(prompts)

        # Extract embeddings
        embeddings = np.array([output.outputs.embedding for output in outputs], dtype=np.float32)

        # L2 normalize
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        embeddings = embeddings / np.maximum(norms, 1e-12)

        return embeddings

    def warmup(self, batch_size: int = 1, seq_len: int = 128) -> float:
        """Run warmup pass."""
        import time

        if not self._loaded:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        logger.info(f"Running vLLM warmup (batch_size={batch_size}, seq_len={seq_len})")

        dummy_ids = np.ones((batch_size, seq_len), dtype=np.int64)
        dummy_mask = np.ones((batch_size, seq_len), dtype=np.int64)

        start = time.perf_counter()
        _ = self.forward(dummy_ids, dummy_mask)
        elapsed_ms = (time.perf_counter() - start) * 1000

        logger.info(f"vLLM warmup complete: {elapsed_ms:.1f}ms")
        return elapsed_ms

    def embedding_dimension(self) -> int:
        """Return the embedding dimension."""
        if self._embedding_dim is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")
        return self._embedding_dim

    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        import torch

        info: dict[str, Any] = {
            "backend": "vllm",
            "device": "cuda",
            "embedding_dimension": self._embedding_dim,
            "model_id": self._model_id,
        }

        if torch.cuda.is_available():
            info["cuda_device_name"] = torch.cuda.get_device_name(0)

        return info

    @property
    def is_loaded(self) -> bool:
        """Return True if model is loaded."""
        return self._loaded

    @property
    def backend_name(self) -> str:
        """Return backend identifier."""
        return "vllm"
