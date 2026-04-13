"""
Health check utilities for qwen3-embedder.

Provides system resource monitoring and health assessment.
"""

import logging
import os
import platform
from typing import Any

logger = logging.getLogger(__name__)


def check_system_resources() -> dict[str, Any]:
    """
    Check system resources for health reporting.

    Returns:
        Dictionary with system resource information
    """
    info: dict[str, Any] = {
        "platform": platform.system(),
        "platform_release": platform.release(),
        "python_version": platform.python_version(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
    }

    # Try to get memory info
    try:
        import psutil

        mem = psutil.virtual_memory()
        info["memory_total_gb"] = round(mem.total / 1e9, 2)
        info["memory_available_gb"] = round(mem.available / 1e9, 2)
        info["memory_percent_used"] = mem.percent
    except ImportError:
        pass

    # Check CUDA if available
    try:
        import torch

        if torch.cuda.is_available():
            info["cuda_available"] = True
            info["cuda_device_count"] = torch.cuda.device_count()
            info["cuda_device_name"] = torch.cuda.get_device_name(0)

            # Memory info
            mem_allocated = torch.cuda.memory_allocated(0)
            mem_reserved = torch.cuda.memory_reserved(0)
            mem_total = torch.cuda.get_device_properties(0).total_memory

            info["cuda_memory_allocated_gb"] = round(mem_allocated / 1e9, 2)
            info["cuda_memory_reserved_gb"] = round(mem_reserved / 1e9, 2)
            info["cuda_memory_total_gb"] = round(mem_total / 1e9, 2)
        else:
            info["cuda_available"] = False

        if torch.backends.mps.is_available():
            info["mps_available"] = True
        else:
            info["mps_available"] = False

    except ImportError:
        info["cuda_available"] = False
        info["mps_available"] = False

    # Check MLX if available
    try:
        import mlx.core as mx

        info["mlx_available"] = True
        info["mlx_default_device"] = str(mx.default_device())
    except ImportError:
        info["mlx_available"] = False

    return info


def check_model_files(model_id: str) -> dict[str, Any]:
    """
    Check if model files are cached locally.

    Args:
        model_id: HuggingFace model ID

    Returns:
        Dictionary with cache information
    """
    try:
        from huggingface_hub import scan_cache_dir

        cache_info = scan_cache_dir()

        for repo in cache_info.repos:
            if repo.repo_id == model_id:
                return {
                    "cached": True,
                    "repo_id": model_id,
                    "size_gb": round(repo.size_on_disk / 1e9, 2),
                    "last_accessed": str(repo.last_accessed),
                }

        return {"cached": False, "repo_id": model_id}

    except Exception as e:
        logger.warning(f"Failed to check model cache: {e}")
        return {"cached": "unknown", "error": str(e)}


def estimate_memory_requirements(model_id: str) -> dict[str, Any]:
    """
    Estimate memory requirements for a model.

    Args:
        model_id: HuggingFace model ID

    Returns:
        Dictionary with memory estimates
    """
    # Rough estimates based on model size
    estimates = {
        "0.6B": {"fp16_gb": 1.5, "fp32_gb": 3.0, "4bit_gb": 0.9},
        "4B": {"fp16_gb": 9.0, "fp32_gb": 18.0, "4bit_gb": 2.5},
        "8B": {"fp16_gb": 17.0, "fp32_gb": 34.0, "4bit_gb": 4.5},
    }

    for size, estimate in estimates.items():
        if size in model_id:
            return {
                "model_id": model_id,
                "estimated_size": size,
                **estimate,
            }

    # Default to 4B estimates
    return {
        "model_id": model_id,
        "estimated_size": "unknown",
        **estimates["4B"],
    }
