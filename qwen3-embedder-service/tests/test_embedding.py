"""Tests for embedding utilities."""

import numpy as np
import pytest

from qwen3_embedder.core.embedding import (
    base64_to_embedding,
    batch_truncate_embeddings,
    cosine_similarity,
    embedding_to_base64,
    get_mrl_dimension,
    l2_normalize,
    truncate_embedding,
    validate_embedding_quality,
)


class TestL2Normalize:
    """Tests for L2 normalization."""

    def test_normalize_single_vector(self):
        """Test normalizing a single vector."""
        vec = np.array([3.0, 4.0])
        normalized = l2_normalize(vec)

        assert normalized.shape == (1, 2)
        assert np.isclose(np.linalg.norm(normalized), 1.0)

    def test_normalize_batch(self):
        """Test normalizing a batch of vectors."""
        vecs = np.array([
            [3.0, 4.0],
            [1.0, 0.0],
            [0.0, 5.0],
        ])
        normalized = l2_normalize(vecs)

        assert normalized.shape == (3, 2)
        for i in range(3):
            assert np.isclose(np.linalg.norm(normalized[i]), 1.0)

    def test_normalize_zero_vector(self):
        """Test normalizing a zero vector doesn't produce NaN."""
        vec = np.array([[0.0, 0.0]])
        normalized = l2_normalize(vec)

        assert not np.any(np.isnan(normalized))

    def test_already_normalized(self):
        """Test that already-normalized vectors remain unchanged."""
        vec = np.array([[0.6, 0.8]])
        normalized = l2_normalize(vec)

        assert np.allclose(vec, normalized)


class TestTruncateEmbedding:
    """Tests for MRL dimension truncation."""

    def test_truncate_to_smaller_dim(self):
        """Test truncating to smaller dimension."""
        emb = np.array([0.6, 0.8, 0.0, 0.0])
        truncated = truncate_embedding(emb, target_dim=2)

        assert truncated.shape[-1] == 2
        assert np.isclose(np.linalg.norm(truncated), 1.0)

    def test_truncate_no_change_when_larger(self):
        """Test no change when target > current dim."""
        emb = np.array([0.6, 0.8])
        truncated = truncate_embedding(emb, target_dim=4)

        assert np.array_equal(emb, truncated)

    def test_truncate_none_returns_original(self):
        """Test None target_dim returns original."""
        emb = np.array([0.6, 0.8])
        truncated = truncate_embedding(emb, target_dim=None)

        assert np.array_equal(emb, truncated)

    def test_batch_truncate(self):
        """Test batch truncation."""
        embs = np.random.randn(10, 2560).astype(np.float32)
        embs = l2_normalize(embs)

        truncated = batch_truncate_embeddings(embs, target_dim=512)

        assert truncated.shape == (10, 512)
        for i in range(10):
            assert np.isclose(np.linalg.norm(truncated[i]), 1.0, atol=1e-5)


class TestCosineSimilarity:
    """Tests for cosine similarity computation."""

    def test_identical_vectors(self):
        """Test similarity of identical vectors is 1."""
        vec = l2_normalize(np.array([[1.0, 2.0, 3.0]]))
        sim = cosine_similarity(vec, vec)

        assert np.isclose(sim[0, 0], 1.0)

    def test_orthogonal_vectors(self):
        """Test similarity of orthogonal vectors is 0."""
        a = l2_normalize(np.array([[1.0, 0.0]]))
        b = l2_normalize(np.array([[0.0, 1.0]]))
        sim = cosine_similarity(a, b)

        assert np.isclose(sim[0, 0], 0.0)

    def test_opposite_vectors(self):
        """Test similarity of opposite vectors is -1."""
        a = l2_normalize(np.array([[1.0, 0.0]]))
        b = l2_normalize(np.array([[-1.0, 0.0]]))
        sim = cosine_similarity(a, b)

        assert np.isclose(sim[0, 0], -1.0)

    def test_batch_similarity(self):
        """Test similarity matrix computation."""
        a = l2_normalize(np.random.randn(3, 128))
        b = l2_normalize(np.random.randn(5, 128))
        sim = cosine_similarity(a, b)

        assert sim.shape == (3, 5)
        assert np.all(sim >= -1.0) and np.all(sim <= 1.0)


class TestValidateEmbeddingQuality:
    """Tests for embedding quality validation."""

    def test_normalized_embeddings(self):
        """Test validation of normalized embeddings."""
        embs = l2_normalize(np.random.randn(10, 256))
        quality = validate_embedding_quality(embs)

        assert quality["is_normalized"] is True
        assert quality["has_nan"] is False
        assert quality["has_inf"] is False

    def test_unnormalized_embeddings(self):
        """Test validation detects unnormalized embeddings."""
        embs = np.random.randn(10, 256) * 10
        quality = validate_embedding_quality(embs)

        assert quality["is_normalized"] is False

    def test_nan_detection(self):
        """Test NaN detection."""
        embs = np.array([[1.0, np.nan, 0.5]])
        quality = validate_embedding_quality(embs)

        assert quality["has_nan"] is True

    def test_inf_detection(self):
        """Test infinity detection."""
        embs = np.array([[1.0, np.inf, 0.5]])
        quality = validate_embedding_quality(embs)

        assert quality["has_inf"] is True


class TestBase64Encoding:
    """Tests for base64 encoding/decoding."""

    def test_roundtrip(self):
        """Test encoding and decoding produces original."""
        emb = np.random.randn(256).astype(np.float32)
        encoded = embedding_to_base64(emb)
        decoded = base64_to_embedding(encoded, dim=256)

        assert np.allclose(emb, decoded)

    def test_encoding_is_string(self):
        """Test encoding produces a string."""
        emb = np.random.randn(128).astype(np.float32)
        encoded = embedding_to_base64(emb)

        assert isinstance(encoded, str)


class TestMRLDimensions:
    """Tests for MRL dimension lookup."""

    def test_known_presets(self):
        """Test known dimension presets."""
        assert get_mrl_dimension("tiny") == 32
        assert get_mrl_dimension("small") == 64
        assert get_mrl_dimension("medium") == 128
        assert get_mrl_dimension("large") == 512

    def test_integer_passthrough(self):
        """Test integer values pass through."""
        assert get_mrl_dimension(256) == 256
        assert get_mrl_dimension(1024) == 1024

    def test_string_integer(self):
        """Test string integers are parsed."""
        assert get_mrl_dimension("512") == 512

    def test_unknown_raises(self):
        """Test unknown preset raises error."""
        with pytest.raises(ValueError):
            get_mrl_dimension("unknown_preset")
