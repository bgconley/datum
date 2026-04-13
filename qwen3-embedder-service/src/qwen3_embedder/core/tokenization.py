"""
Tokenization utilities for qwen3-embedder.

Handles tokenization with LEFT-padding (critical for embeddings),
truncation, and batch processing.

IMPORTANT: Left-padding is required for embedding models because:
- The final token position contains the sequence embedding
- With right-padding, the final position would be a pad token
- With left-padding, the final position is always the actual last token
"""

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class EmbedderTokenizer:
    """
    Tokenizer wrapper for embedding models.

    Ensures correct padding configuration and provides
    convenient methods for batch tokenization.
    """

    def __init__(
        self,
        tokenizer: Any,
        max_length: int = 8192,
    ):
        """
        Initialize tokenizer wrapper.

        Args:
            tokenizer: HuggingFace tokenizer instance
            max_length: Maximum sequence length
        """
        self.tokenizer = tokenizer
        self.max_length = max_length

        # Ensure LEFT padding (critical for embeddings)
        self._configure_padding()

    def _configure_padding(self) -> None:
        """Configure tokenizer for left-padding."""
        # Set padding side to left
        if self.tokenizer.padding_side != "left":
            logger.info(
                f"Changing tokenizer padding_side from '{self.tokenizer.padding_side}' to 'left'"
            )
            self.tokenizer.padding_side = "left"

        # Set truncation side to left as well
        self.tokenizer.truncation_side = "left"

        # Ensure pad token is set
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
            logger.info("Set pad_token to eos_token")

    def tokenize(
        self,
        texts: list[str],
        max_length: int | None = None,
        return_numpy: bool = True,
    ) -> dict[str, Any]:
        """
        Tokenize a batch of texts.

        Args:
            texts: List of text strings to tokenize
            max_length: Optional max length override
            return_numpy: Whether to return numpy arrays

        Returns:
            Dictionary with 'input_ids' and 'attention_mask' keys
        """
        max_len = max_length or self.max_length

        # Tokenize with padding and truncation
        encoded = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=max_len,
            return_tensors="np" if return_numpy else "pt",
        )

        result = {
            "input_ids": encoded["input_ids"],
            "attention_mask": encoded["attention_mask"],
        }

        # Log truncation if any sequences were truncated
        if return_numpy:
            seq_lengths = encoded["attention_mask"].sum(axis=1)
            truncated = (seq_lengths == max_len).sum()
            if truncated > 0:
                logger.debug(f"Truncated {truncated}/{len(texts)} sequences to {max_len} tokens")

        return result

    def tokenize_with_stats(
        self,
        texts: list[str],
        max_length: int | None = None,
    ) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
        """
        Tokenize texts and return statistics.

        Args:
            texts: List of text strings
            max_length: Optional max length override

        Returns:
            Tuple of (encoded_dict, stats_dict)
        """
        max_len = max_length or self.max_length

        encoded = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=max_len,
            return_tensors="np",
        )

        # Calculate statistics
        seq_lengths = encoded["attention_mask"].sum(axis=1)
        truncated_count = int((seq_lengths == max_len).sum())

        stats = {
            "num_texts": len(texts),
            "max_length": max_len,
            "actual_max_length": int(seq_lengths.max()),
            "mean_length": float(seq_lengths.mean()),
            "truncated_count": truncated_count,
            "total_tokens": int(seq_lengths.sum()),
        }

        return {
            "input_ids": encoded["input_ids"],
            "attention_mask": encoded["attention_mask"],
        }, stats

    def count_tokens(self, text: str) -> int:
        """
        Count tokens in a single text without padding.

        Args:
            text: Text to count tokens for

        Returns:
            Number of tokens
        """
        return len(self.tokenizer.encode(text, add_special_tokens=True))

    def estimate_batch_tokens(self, texts: list[str]) -> int:
        """
        Estimate total tokens for a batch (rough, without actual tokenization).

        Args:
            texts: List of texts

        Returns:
            Estimated total token count
        """
        # Rough estimate: ~4 characters per token for English
        total_chars = sum(len(t) for t in texts)
        return total_chars // 4

    @property
    def vocab_size(self) -> int:
        """Return vocabulary size."""
        return self.tokenizer.vocab_size

    @property
    def pad_token_id(self) -> int:
        """Return pad token ID."""
        return self.tokenizer.pad_token_id


def create_tokenizer(
    tokenizer: Any,
    max_length: int = 8192,
) -> EmbedderTokenizer:
    """
    Factory function to create a configured tokenizer.

    Args:
        tokenizer: HuggingFace tokenizer instance
        max_length: Maximum sequence length

    Returns:
        Configured EmbedderTokenizer instance
    """
    return EmbedderTokenizer(tokenizer, max_length)
