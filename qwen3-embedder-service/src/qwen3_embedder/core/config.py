"""
Configuration management for qwen3-embedder.

Loads configuration from YAML profiles with environment variable overrides.
"""

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from qwen3_embedder.core.errors import ConfigurationError


class PyTorchOptions(BaseModel):
    """PyTorch-specific configuration options."""

    device: str = "auto"
    dtype: str = "float16"
    use_flash_attn: bool = True


class VLLMOptions(BaseModel):
    """vLLM-specific configuration options."""

    task: str = "embed"
    tensor_parallel_size: int = 1
    gpu_memory_utilization: float = 0.8
    max_model_len: int = 8192
    trust_remote_code: bool = True


class MLXOptions(BaseModel):
    """MLX-specific configuration options."""

    compile: bool = True


class PromptConfig(BaseModel):
    """Prompt configuration."""

    default_instruction: str = (
        "Given a web search query, retrieve relevant passages that answer the query"
    )


class LimitsConfig(BaseModel):
    """Request limits configuration."""

    max_length: int = 8192
    max_texts_per_request: int = 500
    max_text_chars: int = 32000


class BatchingConfig(BaseModel):
    """Batching configuration."""

    batch_size: int = 32
    max_concurrent_forwards: int = 2


class ProfileConfig(BaseModel):
    """Configuration for a specific model profile."""

    description: str = ""
    backend: Literal["pytorch", "vllm", "mlx"] = "pytorch"
    model_id: str
    embedding_dimension: int = 2560
    hf_tokenizer_id: str | None = None
    prompt: PromptConfig = Field(default_factory=PromptConfig)
    limits: LimitsConfig = Field(default_factory=LimitsConfig)
    batching: BatchingConfig = Field(default_factory=BatchingConfig)
    pytorch_options: PyTorchOptions | None = None
    vllm_options: VLLMOptions | None = None
    mlx_options: MLXOptions | None = None
    performance: dict[str, Any] = Field(default_factory=dict)

    def get_tokenizer_id(self) -> str:
        """Get the tokenizer ID, falling back to model_id if not specified."""
        return self.hf_tokenizer_id or self.model_id


class ServiceSettings(BaseSettings):
    """Service-level settings from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

    # Backend selection
    backend: str = Field(default="auto", alias="QWEN_EMBED_BACKEND")
    profile: str = Field(default="qwen3_4b_cuda", alias="QWEN_EMBED_PROFILE")

    # Server settings
    host: str = Field(default="0.0.0.0", alias="QWEN_EMBED_HOST")
    port: int = Field(default=8010, alias="QWEN_EMBED_PORT")

    # Logging
    log_level: str = Field(default="INFO", alias="QWEN_EMBED_LOG_LEVEL")
    log_format: str = Field(default="json", alias="QWEN_EMBED_LOG_FORMAT")

    # Optional overrides
    device: str | None = Field(default=None, alias="QWEN_EMBED_DEVICE")
    dtype: str | None = Field(default=None, alias="QWEN_EMBED_DTYPE")
    max_length: int | None = Field(default=None, alias="QWEN_EMBED_MAX_LENGTH")
    batch_size: int | None = Field(default=None, alias="QWEN_EMBED_BATCH_SIZE")
    max_concurrent: int | None = Field(default=None, alias="QWEN_EMBED_MAX_CONCURRENT")
    model_id: str | None = Field(default=None, alias="QWEN_EMBED_MODEL_ID")

    # PyTorch-specific
    use_flash_attn: bool | None = Field(default=None, alias="QWEN_EMBED_FLASH_ATTN")

    # vLLM-specific
    tensor_parallel_size: int | None = Field(default=None, alias="QWEN_EMBED_TP_SIZE")
    gpu_memory_utilization: float | None = Field(default=None, alias="QWEN_EMBED_GPU_UTIL")

class AppConfig:
    """
    Application configuration combining profiles and environment settings.

    Usage:
        config = AppConfig.load()
        profile = config.get_profile()
    """

    def __init__(
        self,
        profiles: dict[str, ProfileConfig],
        defaults: dict[str, str],
        settings: ServiceSettings,
    ):
        self.profiles = profiles
        self.defaults = defaults
        self.settings = settings
        self._active_profile: ProfileConfig | None = None

    @classmethod
    def load(cls, config_path: Path | None = None) -> "AppConfig":
        """
        Load configuration from YAML file and environment variables.

        Args:
            config_path: Path to profiles YAML file. If None, auto-discovers.

        Returns:
            Fully loaded AppConfig instance.
        """
        settings = ServiceSettings()

        # Find config file
        if config_path is None:
            config_path = cls._find_config_file()

        if config_path is None or not config_path.exists():
            raise ConfigurationError(
                f"Configuration file not found. Searched paths: {cls._get_search_paths()}"
            )

        # Load YAML profiles
        with open(config_path) as f:
            raw_config = yaml.safe_load(f)

        if "profiles" not in raw_config:
            raise ConfigurationError("Configuration file must contain 'profiles' key")

        # Parse profiles
        profiles: dict[str, ProfileConfig] = {}
        for name, profile_data in raw_config["profiles"].items():
            try:
                profiles[name] = ProfileConfig(**profile_data)
            except Exception as e:
                raise ConfigurationError(f"Invalid profile '{name}': {e}") from e

        # Parse defaults
        defaults = raw_config.get("defaults", {})

        return cls(profiles=profiles, defaults=defaults, settings=settings)

    @staticmethod
    def _find_config_file() -> Path | None:
        """Find the configuration file in standard locations."""
        for search_path in AppConfig._get_search_paths():
            if search_path.exists():
                return search_path
        return None

    @staticmethod
    def _get_search_paths() -> list[Path]:
        """Get list of paths to search for config file."""
        # Start from the current file's location and work up
        current_dir = Path(__file__).parent
        project_root = current_dir.parent.parent.parent  # src/qwen3_embedder/core -> project root

        return [
            project_root / "config" / "embedder_profiles.yaml",
            Path.cwd() / "config" / "embedder_profiles.yaml",
            Path.cwd() / "embedder_profiles.yaml",
            Path("/etc/qwen3-embedder/embedder_profiles.yaml"),
        ]

    def get_profile(self, profile_name: str | None = None) -> ProfileConfig:
        """
        Get a profile by name with environment variable overrides applied.

        Args:
            profile_name: Profile name. If None, uses settings.profile or auto-selects.

        Returns:
            ProfileConfig with environment overrides applied.
        """
        # Determine profile name
        if profile_name is None:
            profile_name = self.settings.profile

        # Handle 'auto' backend selection
        if profile_name == "auto" or self.settings.backend == "auto":
            profile_name = self._auto_select_profile()

        if profile_name not in self.profiles:
            available = list(self.profiles.keys())
            raise ConfigurationError(
                f"Profile '{profile_name}' not found. Available: {available}"
            )

        # Get base profile and apply overrides
        profile = self.profiles[profile_name].model_copy(deep=True)
        self._apply_env_overrides(profile)
        self._active_profile = profile

        return profile

    def _auto_select_profile(self) -> str:
        """Auto-select best profile based on available hardware."""
        backend = self.settings.backend

        if backend == "auto":
            # Detect available backends
            backend = self._detect_best_backend()

        # Use default profile for detected backend
        if backend in self.defaults:
            return self.defaults[backend]

        # Fallback
        return "qwen3_4b_cuda"

    def _detect_best_backend(self) -> str:
        """Detect the best available backend."""
        # Try PyTorch with CUDA
        try:
            import torch

            if torch.cuda.is_available():
                return "pytorch"
            if torch.backends.mps.is_available():
                return "pytorch"
        except ImportError:
            pass

        # Try vLLM
        try:
            import vllm  # noqa: F401

            return "vllm"
        except ImportError:
            pass

        # Try MLX
        try:
            import platform

            import mlx.core  # noqa: F401

            if platform.machine() == "arm64" and platform.system() == "Darwin":
                return "mlx"
        except ImportError:
            pass

        # Fallback to PyTorch (will use CPU)
        return "pytorch"

    def _apply_env_overrides(self, profile: ProfileConfig) -> None:
        """Apply environment variable overrides to a profile."""
        s = self.settings

        # Model override
        if s.model_id:
            profile.model_id = s.model_id

        # Limits overrides
        if s.max_length:
            profile.limits.max_length = s.max_length

        # Batching overrides
        if s.batch_size:
            profile.batching.batch_size = s.batch_size
        if s.max_concurrent:
            profile.batching.max_concurrent_forwards = s.max_concurrent

        # PyTorch-specific overrides
        if profile.backend == "pytorch" and profile.pytorch_options:
            if s.device:
                profile.pytorch_options.device = s.device
            if s.dtype:
                profile.pytorch_options.dtype = s.dtype
            if s.use_flash_attn is not None:
                profile.pytorch_options.use_flash_attn = s.use_flash_attn

        # vLLM-specific overrides
        if profile.backend == "vllm" and profile.vllm_options:
            if s.tensor_parallel_size:
                profile.vllm_options.tensor_parallel_size = s.tensor_parallel_size
            if s.gpu_memory_utilization:
                profile.vllm_options.gpu_memory_utilization = s.gpu_memory_utilization

    @property
    def active_profile(self) -> ProfileConfig | None:
        """Get the currently active profile (after get_profile has been called)."""
        return self._active_profile


def get_config() -> AppConfig:
    """
    Get the application configuration singleton.

    This is a convenience function for getting configuration
    in FastAPI dependency injection.
    """
    return AppConfig.load()
