"""Tests for content-addressed blob storage."""

from datum.services.blob_store import compute_blob_path, store_blob


def test_compute_blob_path_uses_shards():
    hash_hex = "abcdef1234567890" * 4
    assert compute_blob_path(hash_hex, ".pdf") == f"ab/cd/{hash_hex}.pdf"


def test_store_blob_is_idempotent(tmp_path):
    first = store_blob(b"same content", ".txt", tmp_path)
    second = store_blob(b"same content", ".txt", tmp_path)
    assert first["content_hash"] == second["content_hash"]
    assert first["blob_path"] == second["blob_path"]
    assert (tmp_path / str(first["blob_path"])).exists()
