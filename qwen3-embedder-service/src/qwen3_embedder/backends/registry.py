"""
Backend registry and auto-detection for qwen3-embedder.

Handles backend selection based on:
1. Explicit configuration (QWEN_EMBED_BACKEND env var)
2. Profile backend specification
3. Auto-detection based on available hardware
"""

import logging
import platform
from typing import Literal, Optional

from qwen3_embedder.backends.base import EmbedderBackend
from qwen3_embedder.core.config import ProfileConfig
from qwen3_embedder.core.errors import BackendError, ConfigurationError

logger = logging.getLogger(__name__)

BackendType = Literal["pytorch", "vllm", "mlx"]


class BackendRegistry:
    """
    Registry for backend implementations with auto-detection.

    Priority order for auto-detection:
    1. PyTorch with CUDA (if available)
    2. PyTorch with MPS (if on Apple Silicon)
    3. vLLM (if available and CUDA present)
    4. MLX (if on Apple Silicon)
    5. PyTorch with CPU (fallback)
    """

    _instance: Optional["BackendRegistry"] = None
    _backend: EmbedderBackend | None = None

    def __new__(cls) -> "BackendRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_backend(
        cls,
        profile: ProfileConfig,
        backend_override: str | None = None,
    ) -> EmbedderBackend:
        """
        Get or create the appropriate backend for the given profile.

        Args:
            profile: Configuration profile with backend settings
            backend_override: Override backend type ("pytorch", "vllm", "mlx", or "auto")

        Returns:
            Initialized EmbedderBackend instance
        """
        registry = cls()

        # Determine backend type
        backend_type = backend_override or profile.backend
        if backend_type == "auto":
            backend_type = cls._detect_best_backend()

        logger.info(f"Selected backend: {backend_type}")

        # Create backend if not cached or different type
        if registry._backend is None or registry._backend.backend_name != backend_type:
            registry._backend = cls._create_backend(backend_type, profile)

        return registry._backend

    @classmethod
    def _detect_best_backend(cls) -> BackendType:
        """
        Detect the best available backend based on hardware.

        Returns:
            Backend type string
        """
        # Check for PyTorch with CUDA first (highest priority for NVIDIA GPUs)
        if cls._is_cuda_available():
            logger.info("CUDA detected, using PyTorch backend")
            return "pytorch"

        # Check for MPS on Apple Silicon
        if cls._is_mps_available():
            # On Apple Silicon, prefer MLX if available for better performance
            if cls._is_mlx_available():
                logger.info("Apple Silicon detected, using MLX backend")
                return "mlx"
            logger.info("Apple Silicon detected, using PyTorch MPS backend")
            return "pytorch"

        # Check for vLLM (requires CUDA)
        if cls._is_vllm_available():
            logger.info("vLLM detected, using vLLM backend")
            return "vllm"

        # Fallback to PyTorch CPU
        logger.warning("No GPU detected, falling back to PyTorch CPU backend")
        return "pytorch"

    @classmethod
    def _create_backend(cls, backend_type: BackendType, profile: ProfileConfig) -> EmbedderBackend:
        """
        Create a backend instance of the specified type.

        Args:
            backend_type: Type of backend to create
            profile: Configuration profile

        Returns:
            Initialized backend instance
        """
        if backend_type == "pytorch":
            return cls._create_pytorch_backend(profile)
        elif backend_type == "vllm":
            return cls._create_vllm_backend(profile)
        elif backend_type == "mlx":
            return cls._create_mlx_backend(profile)
        else:
            raise ConfigurationError(f"Unknown backend type: {backend_type}")

    @classmethod
    def _create_pytorch_backend(cls, profile: ProfileConfig) -> EmbedderBackend:
        """Create PyTorch backend."""
        try:
            from qwen3_embedder.backends.pytorch_backend import PyTorchBackend
        except ImportError as e:
            raise BackendError(
                "PyTorch backend not available. Install with: pip install torch"
            ) from e

        options = profile.pytorch_options
        device = options.device if options else "auto"

        backend = PyTorchBackend(device=device if device != "auto" else None)

        # Prepare load kwargs
        load_kwargs = {}
        if options:
            if options.dtype == "float16":
                load_kwargs["dtype"] = "float16"
            elif options.dtype == "bfloat16":
                load_kwargs["dtype"] = "bfloat16"
            elif options.dtype == "float32":
                load_kwargs["dtype"] = "float32"
            load_kwargs["use_flash_attn"] = options.use_flash_attn

        backend.load_model(profile.model_id, **load_kwargs)
        return backend

    @classmethod
    def _create_vllm_backend(cls, profile: ProfileConfig) -> EmbedderBackend:
        """Create vLLM backend."""
        try:
            from qwen3_embedder.backends.vllm_backend import VLLMBackend
        except ImportError as e:
            raise BackendError(
                "vLLM backend not available. Install with: pip install vllm"
            ) from e

        options = profile.vllm_options
        backend = VLLMBackend()

        load_kwargs = {}
        if options:
            load_kwargs["tensor_parallel_size"] = options.tensor_parallel_size
            load_kwargs["gpu_memory_utilization"] = options.gpu_memory_utilization
            load_kwargs["max_model_len"] = options.max_model_len
            load_kwargs["trust_remote_code"] = options.trust_remote_code

        backend.load_model(profile.model_id, **load_kwargs)
        return backend

    @classmethod
    def _create_mlx_backend(cls, profile: ProfileConfig) -> EmbedderBackend:
        """Create MLX backend."""
        try:
            from qwen3_embedder.backends.mlx_backend import MLXBackend
        except ImportError as e:
            raise BackendError(
                "MLX backend not available. Install with: pip install mlx mlx-lm"
            ) from e

        backend = MLXBackend()

        load_kwargs = {}
        if profile.hf_tokenizer_id:
            load_kwargs["hf_tokenizer_id"] = profile.hf_tokenizer_id

        backend.load_model(profile.model_id, **load_kwargs)
        return backend

    @staticmethod
    def _is_cuda_available() -> bool:
        """Check if CUDA is available via PyTorch."""
        try:
            import torch

            return torch.cuda.is_available()
        except ImportError:
            return False

    @staticmethod
    def _is_mps_available() -> bool:
        """Check if MPS (Metal Performance Shaders) is available."""
        try:
            import torch

            return torch.backends.mps.is_available()
        except (ImportError, AttributeError):
            return False

    @staticmethod
    def _is_vllm_available() -> bool:
        """Check if vLLM is available."""
        try:
            # vLLM requires CUDA
            import torch
            import vllm  # noqa: F401

            return torch.cuda.is_available()
        except ImportError:
            return False

    @staticmethod
    def _is_mlx_available() -> bool:
        """Check if MLX is available (Apple Silicon only)."""
        if platform.machine() != "arm64" or platform.system() != "Darwin":
            return False
        try:
            import mlx.core  # noqa: F401

            return True
        except ImportError:
            return False

    @classmethod
    def reset(cls) -> None:
        """Reset the registry, clearing any cached backend."""
        if cls._instance is not None:
            cls._instance._backend = None


def get_backend(
    profile: ProfileConfig,
    backend_override: str | None = None,
) -> EmbedderBackend:
    """
    Convenience function to get a backend instance.

    Args:
        profile: Configuration profile
        backend_override: Optional backend type override

    Returns:
        Initialized EmbedderBackend
    """
    return BackendRegistry.get_backend(profile, backend_override)
