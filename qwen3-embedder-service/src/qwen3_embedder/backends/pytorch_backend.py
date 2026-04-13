"""
PyTorch Backend - Primary implementation for cross-platform support.

This is the PRIMARY backend supporting CUDA, MPS (Apple Silicon), and CPU.
It uses HuggingFace AutoModel for loading Qwen3-Embedding models and
implements last-token pooling with L2 normalization.

Key differences from reranker:
- Uses AutoModel instead of AutoModelForCausalLM
- Extracts last_hidden_state instead of logits
- Returns L2-normalized embeddings instead of scores
"""

import logging
import time
from typing import Any

import numpy as np
import torch
import torch.nn.functional as functional

logger = logging.getLogger(__name__)


def last_token_pool(
    last_hidden_states: torch.Tensor,
    attention_mask: torch.Tensor,
) -> torch.Tensor:
    """
    Extract embeddings from the last token position.

    With left-padding (recommended), the last position is always valid.
    With right-padding, we find the actual last token per sequence.

    Args:
        last_hidden_states: Hidden states from model, shape [batch, seq_len, hidden_dim]
        attention_mask: Attention mask, shape [batch, seq_len]

    Returns:
        Embeddings of shape [batch, hidden_dim]
    """
    # Check if left-padded (all sequences have valid last token)
    left_padding = attention_mask[:, -1].sum() == attention_mask.shape[0]

    if left_padding:
        # Simple case: last position is always the actual last token
        return last_hidden_states[:, -1]
    else:
        # Right-padded: find actual last token position per sequence
        sequence_lengths = attention_mask.sum(dim=1) - 1
        batch_size = last_hidden_states.shape[0]
        return last_hidden_states[
            torch.arange(batch_size, device=last_hidden_states.device),
            sequence_lengths,
        ]


class PyTorchBackend:
    """
    PyTorch backend supporting CUDA, MPS, and CPU - PRIMARY BACKEND.

    This backend uses HuggingFace's AutoModel to load Qwen3-Embedding models
    and implements the standard embedding extraction pipeline:
    1. Forward pass to get hidden states
    2. Last-token pooling to extract final token embedding
    3. L2 normalization

    Supports Flash Attention 2 on compatible CUDA GPUs for faster inference.
    """

    def __init__(self, device: str | None = None):
        """
        Initialize PyTorch backend.

        Args:
            device: Device to use ("cuda", "mps", "cpu", or None for auto-detect)
        """
        self._model = None
        self._tokenizer = None
        self._device: torch.device | None = None
        self._loaded = False
        self._requested_device = device
        self._embedding_dim: int | None = None
        self._model_id: str | None = None
        self._dtype: torch.dtype | None = None
        self._use_flash_attn = False

    def _select_device(self) -> torch.device:
        """
        Auto-select best available device.

        Priority: CUDA > MPS > CPU
        """
        if self._requested_device:
            device = torch.device(self._requested_device)
            logger.info(f"Using explicitly requested device: {device}")
            return device

        if torch.cuda.is_available():
            device = torch.device("cuda")
            gpu_name = torch.cuda.get_device_name(0)
            logger.info(f"Auto-selected CUDA device: {gpu_name}")
        elif torch.backends.mps.is_available():
            device = torch.device("mps")
            logger.info("Auto-selected MPS (Apple Silicon)")
        else:
            device = torch.device("cpu")
            logger.warning("No GPU available, using CPU - inference will be slow")

        return device

    def _supports_flash_attn(self) -> bool:
        """Check if Flash Attention 2 is available and supported."""
        if not torch.cuda.is_available():
            return False

        try:
            import flash_attn  # noqa: F401

            # Flash Attention requires compute capability >= 8.0 (Ampere+)
            cc = torch.cuda.get_device_capability()
            if cc[0] >= 8:
                logger.info(f"Flash Attention 2 available (compute capability {cc[0]}.{cc[1]})")
                return True
            else:
                logger.info(
                    f"Flash Attention 2 not supported (compute capability {cc[0]}.{cc[1]} < 8.0)"
                )
                return False
        except ImportError:
            logger.info("Flash Attention 2 not installed")
            return False

    def load_model(self, model_id: str, **kwargs: Any) -> None:
        """
        Load PyTorch embedding model.

        Args:
            model_id: HuggingFace model ID (e.g., "Qwen/Qwen3-Embedding-4B")
            **kwargs: Additional options:
                - dtype: "float16", "bfloat16", or "float32"
                - use_flash_attn: Whether to use Flash Attention 2
        """
        from transformers import AutoModel, AutoTokenizer

        self._model_id = model_id
        self._device = self._select_device()

        # Determine dtype based on device
        dtype_str = kwargs.get("dtype", "float16")
        if self._device.type == "cuda":
            if dtype_str == "bfloat16":
                self._dtype = torch.bfloat16
            elif dtype_str == "float16":
                self._dtype = torch.float16
            else:
                self._dtype = torch.float32

            # Check Flash Attention support
            use_flash = kwargs.get("use_flash_attn", True)
            self._use_flash_attn = use_flash and self._supports_flash_attn()
            attn_impl = "flash_attention_2" if self._use_flash_attn else "eager"
        elif self._device.type == "mps":
            # MPS works best with float16
            self._dtype = torch.float16 if dtype_str != "float32" else torch.float32
            attn_impl = "eager"
            self._use_flash_attn = False
        else:
            # CPU uses float32
            self._dtype = torch.float32
            attn_impl = "eager"
            self._use_flash_attn = False

        logger.info(
            f"Loading PyTorch model: {model_id} "
            f"(device={self._device}, dtype={self._dtype}, attn={attn_impl})"
        )

        # Load tokenizer with LEFT padding (critical for embeddings)
        self._tokenizer = AutoTokenizer.from_pretrained(model_id, padding_side="left")

        # Ensure pad token is set
        if self._tokenizer.pad_token is None:
            self._tokenizer.pad_token = self._tokenizer.eos_token
            logger.info("Set pad_token to eos_token")

        # Load model - NOTE: AutoModel, NOT AutoModelForCausalLM
        load_kwargs: dict[str, Any] = {
            "torch_dtype": self._dtype,
            "trust_remote_code": True,
        }

        # Set attention implementation
        if attn_impl != "eager":
            load_kwargs["attn_implementation"] = attn_impl

        # Use device_map for CUDA to enable efficient loading
        if self._device.type == "cuda":
            load_kwargs["device_map"] = "auto"

        self._model = AutoModel.from_pretrained(model_id, **load_kwargs)

        # Move to device if not using device_map
        if self._device.type != "cuda":
            self._model = self._model.to(self._device)

        self._model.eval()

        # Get embedding dimension from model config
        self._embedding_dim = self._model.config.hidden_size

        self._loaded = True
        logger.info(
            f"PyTorch backend loaded successfully: "
            f"device={self._device}, embedding_dim={self._embedding_dim}"
        )

    def get_tokenizer(self) -> Any:
        """Return the tokenizer."""
        if self._tokenizer is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")
        return self._tokenizer

    @torch.no_grad()
    def forward(
        self,
        input_ids: np.ndarray,
        attention_mask: np.ndarray,
    ) -> np.ndarray:
        """
        Run forward pass and return L2-normalized embeddings.

        Unlike reranker (which extracts yes/no logits), we:
        1. Get last_hidden_state from model
        2. Apply last_token_pool to extract final token embedding
        3. L2-normalize the embeddings

        Args:
            input_ids: Token IDs, shape [batch, seq_len], dtype int64
            attention_mask: Attention mask, shape [batch, seq_len], dtype int64

        Returns:
            L2-normalized embeddings, shape [batch, embedding_dim], dtype float32
        """
        if not self._loaded:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        # Convert to tensors and move to device
        input_ids_t = torch.from_numpy(input_ids).to(self._device)
        attention_mask_t = torch.from_numpy(attention_mask).to(self._device)

        # Forward pass - get hidden states, not logits
        outputs = self._model(
            input_ids=input_ids_t,
            attention_mask=attention_mask_t,
            return_dict=True,
        )

        # Extract embeddings via last-token pooling
        embeddings = last_token_pool(outputs.last_hidden_state, attention_mask_t)

        # L2 normalize
        embeddings = functional.normalize(embeddings, p=2, dim=1)

        # Convert to numpy (always float32 for consistency across backends)
        return embeddings.float().cpu().numpy()

    def warmup(self, batch_size: int = 1, seq_len: int = 128) -> float:
        """
        Run warmup pass to initialize CUDA kernels.

        Args:
            batch_size: Number of sequences for warmup
            seq_len: Sequence length for warmup

        Returns:
            Warmup time in milliseconds
        """
        if not self._loaded:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        logger.info(f"Running PyTorch warmup (batch_size={batch_size}, seq_len={seq_len})")

        # Create dummy inputs
        dummy_ids = np.ones((batch_size, seq_len), dtype=np.int64)
        dummy_mask = np.ones((batch_size, seq_len), dtype=np.int64)

        # Run warmup
        start = time.perf_counter()
        _ = self.forward(dummy_ids, dummy_mask)

        # Synchronize if using CUDA
        if self._device is not None and self._device.type == "cuda":
            torch.cuda.synchronize()

        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(f"PyTorch warmup complete: {elapsed_ms:.1f}ms")

        return elapsed_ms

    def embedding_dimension(self) -> int:
        """Return the embedding dimension."""
        if self._embedding_dim is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")
        return self._embedding_dim

    def device_info(self) -> dict[str, Any]:
        """Return device information for health checks."""
        info: dict[str, Any] = {
            "backend": "pytorch",
            "backend_version": torch.__version__,
            "device": str(self._device) if self._device else "not_loaded",
            "embedding_dimension": self._embedding_dim,
            "model_id": self._model_id,
            "dtype": str(self._dtype) if self._dtype else None,
            "flash_attention": self._use_flash_attn,
            "cuda_available": torch.cuda.is_available(),
            "mps_available": torch.backends.mps.is_available(),
        }

        if self._device is not None and self._device.type == "cuda":
            info["cuda_device_name"] = torch.cuda.get_device_name(0)
            info["cuda_memory_allocated_gb"] = torch.cuda.memory_allocated() / 1e9
            info["cuda_memory_reserved_gb"] = torch.cuda.memory_reserved() / 1e9

        return info

    @property
    def is_loaded(self) -> bool:
        """Return True if model is loaded."""
        return self._loaded

    @property
    def backend_name(self) -> str:
        """Return backend identifier."""
        return "pytorch"
