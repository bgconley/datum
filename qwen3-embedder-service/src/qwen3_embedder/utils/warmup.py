"""
Warmup utilities for qwen3-embedder.

Runs warmup passes to initialize CUDA kernels and JIT compilation.
"""

import logging
from typing import Any

from qwen3_embedder.backends.base import EmbedderBackend

logger = logging.getLogger(__name__)


def run_warmup(
    backend: EmbedderBackend,
    batch_sizes: list[int] | None = None,
    seq_len: int = 128,
) -> dict[str, Any]:
    """
    Run warmup passes with various batch sizes.

    This initializes CUDA kernels, JIT compiles graphs, and
    ensures stable latency for subsequent requests.

    Args:
        backend: Backend to warm up
        batch_sizes: List of batch sizes to test (default: [1, 4, 8])
        seq_len: Sequence length for warmup

    Returns:
        Dictionary with warmup statistics
    """
    if batch_sizes is None:
        batch_sizes = [1, 4, 8]

    results = {
        "backend": backend.backend_name,
        "warmup_passes": [],
        "total_time_ms": 0.0,
    }

    logger.info(f"Starting warmup for {backend.backend_name} backend")

    for batch_size in batch_sizes:
        try:
            elapsed_ms = backend.warmup(batch_size=batch_size, seq_len=seq_len)
            results["warmup_passes"].append({
                "batch_size": batch_size,
                "seq_len": seq_len,
                "elapsed_ms": elapsed_ms,
            })
            results["total_time_ms"] += elapsed_ms
            logger.info(f"Warmup pass: batch_size={batch_size}, elapsed={elapsed_ms:.1f}ms")
        except Exception as e:
            logger.warning(f"Warmup failed for batch_size={batch_size}: {e}")
            results["warmup_passes"].append({
                "batch_size": batch_size,
                "seq_len": seq_len,
                "error": str(e),
            })

    logger.info(f"Warmup complete: total_time={results['total_time_ms']:.1f}ms")

    return results
