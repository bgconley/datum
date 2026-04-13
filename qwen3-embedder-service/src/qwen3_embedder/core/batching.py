"""
Batching utilities for qwen3-embedder.

Handles batch processing with configurable batch sizes,
concurrency control via semaphores, and efficient memory management.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class BatchProcessor:
    """
    Process embeddings in batches with concurrency control.

    Uses a semaphore to limit concurrent forward passes and
    prevent GPU memory exhaustion.
    """

    def __init__(
        self,
        batch_size: int = 32,
        max_concurrent: int = 2,
    ):
        """
        Initialize batch processor.

        Args:
            batch_size: Maximum batch size for forward pass
            max_concurrent: Maximum concurrent forward passes
        """
        self.batch_size = batch_size
        self.max_concurrent = max_concurrent
        self._semaphore: asyncio.Semaphore | None = None

    @property
    def semaphore(self) -> asyncio.Semaphore:
        """Get or create semaphore (lazy initialization for async context)."""
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.max_concurrent)
        return self._semaphore

    def process_sync(
        self,
        input_ids: np.ndarray,
        attention_mask: np.ndarray,
        forward_fn: Callable[[np.ndarray, np.ndarray], np.ndarray],
    ) -> tuple[np.ndarray, dict[str, Any]]:
        """
        Process embeddings synchronously in batches.

        Args:
            input_ids: All input IDs, shape [total, seq_len]
            attention_mask: All attention masks, shape [total, seq_len]
            forward_fn: Function to call for each batch

        Returns:
            Tuple of (all_embeddings, stats)
        """
        total = input_ids.shape[0]
        num_batches = (total + self.batch_size - 1) // self.batch_size

        embeddings_list: list[np.ndarray] = []
        total_time_ms = 0.0

        for i in range(num_batches):
            start_idx = i * self.batch_size
            end_idx = min((i + 1) * self.batch_size, total)

            batch_ids = input_ids[start_idx:end_idx]
            batch_mask = attention_mask[start_idx:end_idx]

            start = time.perf_counter()
            batch_embeddings = forward_fn(batch_ids, batch_mask)
            elapsed_ms = (time.perf_counter() - start) * 1000
            total_time_ms += elapsed_ms

            embeddings_list.append(batch_embeddings)

            logger.debug(
                f"Processed batch {i + 1}/{num_batches}: "
                f"{end_idx - start_idx} items in {elapsed_ms:.1f}ms"
            )

        all_embeddings = np.vstack(embeddings_list)

        stats = {
            "total_items": total,
            "num_batches": num_batches,
            "batch_size": self.batch_size,
            "total_time_ms": total_time_ms,
            "avg_batch_time_ms": total_time_ms / num_batches if num_batches > 0 else 0,
            "throughput_items_per_sec": total / (total_time_ms / 1000) if total_time_ms > 0 else 0,
        }

        return all_embeddings, stats

    async def process_async(
        self,
        input_ids: np.ndarray,
        attention_mask: np.ndarray,
        forward_fn: Callable[[np.ndarray, np.ndarray], np.ndarray],
    ) -> tuple[np.ndarray, dict[str, Any]]:
        """
        Process embeddings asynchronously with concurrency control.

        Uses semaphore to limit concurrent forward passes.

        Args:
            input_ids: All input IDs, shape [total, seq_len]
            attention_mask: All attention masks, shape [total, seq_len]
            forward_fn: Function to call for each batch

        Returns:
            Tuple of (all_embeddings, stats)
        """
        total = input_ids.shape[0]
        num_batches = (total + self.batch_size - 1) // self.batch_size

        # Create batch tasks
        async def process_batch(batch_idx: int) -> tuple[int, np.ndarray, float]:
            """Process a single batch with semaphore guard."""
            async with self.semaphore:
                start_idx = batch_idx * self.batch_size
                end_idx = min((batch_idx + 1) * self.batch_size, total)

                batch_ids = input_ids[start_idx:end_idx]
                batch_mask = attention_mask[start_idx:end_idx]

                # Run forward pass in executor to avoid blocking
                loop = asyncio.get_event_loop()
                start = time.perf_counter()
                batch_embeddings = await loop.run_in_executor(
                    None, forward_fn, batch_ids, batch_mask
                )
                elapsed_ms = (time.perf_counter() - start) * 1000

                return batch_idx, batch_embeddings, elapsed_ms

        # Process all batches
        start_total = time.perf_counter()
        tasks = [process_batch(i) for i in range(num_batches)]
        results = await asyncio.gather(*tasks)
        total_time_ms = (time.perf_counter() - start_total) * 1000

        # Sort by batch index and collect embeddings
        results.sort(key=lambda x: x[0])
        embeddings_list = [r[1] for r in results]
        batch_times = [r[2] for r in results]

        all_embeddings = np.vstack(embeddings_list)

        stats = {
            "total_items": total,
            "num_batches": num_batches,
            "batch_size": self.batch_size,
            "max_concurrent": self.max_concurrent,
            "total_time_ms": total_time_ms,
            "avg_batch_time_ms": sum(batch_times) / len(batch_times) if batch_times else 0,
            "throughput_items_per_sec": total / (total_time_ms / 1000) if total_time_ms > 0 else 0,
        }

        return all_embeddings, stats


def chunk_texts(
    texts: list[str],
    max_batch_size: int,
    max_tokens_estimate: int | None = None,
) -> list[list[str]]:
    """
    Chunk texts into batches.

    Args:
        texts: List of texts to chunk
        max_batch_size: Maximum texts per batch
        max_tokens_estimate: Optional max tokens per batch (uses character estimate)

    Returns:
        List of text batches
    """
    if max_tokens_estimate is None:
        # Simple chunking by count
        return [
            texts[i : i + max_batch_size]
            for i in range(0, len(texts), max_batch_size)
        ]

    # Token-aware chunking (rough estimate: 4 chars per token)
    batches: list[list[str]] = []
    current_batch: list[str] = []
    current_tokens = 0

    for text in texts:
        text_tokens = len(text) // 4
        if current_tokens + text_tokens > max_tokens_estimate or len(current_batch) >= max_batch_size:
            if current_batch:
                batches.append(current_batch)
            current_batch = [text]
            current_tokens = text_tokens
        else:
            current_batch.append(text)
            current_tokens += text_tokens

    if current_batch:
        batches.append(current_batch)

    return batches


def estimate_memory_usage(
    batch_size: int,
    seq_len: int,
    embedding_dim: int,
    dtype_bytes: int = 2,  # float16
) -> dict[str, float]:
    """
    Estimate GPU memory usage for a batch.

    Args:
        batch_size: Number of sequences
        seq_len: Sequence length
        embedding_dim: Embedding dimension
        dtype_bytes: Bytes per element (2 for float16, 4 for float32)

    Returns:
        Dictionary with memory estimates in GB
    """
    # Input tensors (input_ids + attention_mask as int64)
    input_bytes = batch_size * seq_len * 8 * 2

    # Hidden states during forward pass (rough estimate)
    # Assuming ~36 layers with hidden_dim storage
    hidden_bytes = batch_size * seq_len * embedding_dim * dtype_bytes * 36

    # Output embeddings
    output_bytes = batch_size * embedding_dim * 4  # Always float32 output

    return {
        "input_gb": input_bytes / 1e9,
        "hidden_gb": hidden_bytes / 1e9,
        "output_gb": output_bytes / 1e9,
        "total_estimate_gb": (input_bytes + hidden_bytes + output_bytes) / 1e9,
    }
