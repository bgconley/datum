"""
Backend Protocol definition for qwen3-embedder.

All backends must implement the EmbedderBackend Protocol to ensure
consistent behavior and enable parity testing.
"""

from typing import Any, Protocol, runtime_checkable

import numpy as np


@runtime_checkable
class EmbedderBackend(Protocol):
    """
    Protocol defining the interface all backends must implement.

    Design Notes:
    - All backends must produce numerically equivalent embeddings (within tolerance)
    - PyTorch is the reference implementation; others are validated against it
    - Forward pass returns L2-normalized embeddings as numpy arrays
    - All backends use HuggingFace tokenizers for consistency
    """

    def load_model(self, model_id: str, **kwargs: Any) -> None:
        """
        Load model and tokenizer. Called once at startup.

        Args:
            model_id: HuggingFace model ID or local path
                     MLX: "mlx-community/Qwen3-Embedding-4B-4bit-DWQ"
                     PyTorch: "Qwen/Qwen3-Embedding-4B"
            **kwargs: Backend-specific options (dtype, device, etc.)
        """
        ...

    def get_tokenizer(self) -> Any:
        """
        Return the tokenizer (HuggingFace-compatible interface expected).

        The tokenizer should be configured with:
        - padding_side = "left" (critical for embeddings)
        - truncation_side = "left"
        """
        ...

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
            np.ndarray of shape [batch, embedding_dim], dtype float32
            Embeddings are already L2-normalized.
        """
        ...

    def warmup(self, batch_size: int = 1, seq_len: int = 128) -> float:
        """
        Run warmup pass to initialize CUDA kernels / compile graphs.

        Args:
            batch_size: Number of sequences for warmup
            seq_len: Sequence length for warmup

        Returns:
            Warmup time in milliseconds
        """
        ...

    def embedding_dimension(self) -> int:
        """Return the embedding dimension (e.g., 2560 for 4B model)."""
        ...

    def device_info(self) -> dict[str, Any]:
        """
        Return device information for health checks and logging.

        Should include at minimum:
        - backend: str (e.g., "pytorch", "vllm", "mlx")
        - device: str (e.g., "cuda:0", "mps", "cpu")
        - embedding_dimension: int
        """
        ...

    @property
    def is_loaded(self) -> bool:
        """Return True if model is loaded and ready for inference."""
        ...

    @property
    def backend_name(self) -> str:
        """Return backend identifier (pytorch, vllm, mlx)."""
        ...


class BackendCapabilities:
    """
    Declare capabilities for each backend type.

    Used for backend selection and validation.
    """

    PYTORCH = {
        "platforms": ["darwin_arm64", "darwin_x86_64", "linux_x86_64", "win32"],
        "devices": ["cuda", "mps", "cpu"],
        "quantization": ["fp16", "bf16", "fp32"],
        "flash_attention": True,  # CUDA only
        "batch_inference": True,
    }

    VLLM = {
        "platforms": ["linux_x86_64"],
        "devices": ["cuda"],
        "quantization": ["fp16", "awq", "gptq"],
        "flash_attention": True,
        "continuous_batching": True,
        "tensor_parallelism": True,
    }

    MLX = {
        "platforms": ["darwin_arm64"],
        "quantization": ["4bit", "8bit", "fp16"],
        "batch_inference": True,
        "memory_efficient": True,
        "models": [
            "mlx-community/Qwen3-Embedding-0.6B-4bit-DWQ",
            "mlx-community/Qwen3-Embedding-4B-4bit-DWQ",
            "mlx-community/Qwen3-Embedding-8B-4bit-DWQ",
        ],
    }
