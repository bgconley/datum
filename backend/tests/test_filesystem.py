import pytest
from pathlib import Path

from datum.services.filesystem import compute_content_hash, atomic_write, read_manifest, write_manifest


class TestContentHash:
    def test_hash_bytes(self):
        h = compute_content_hash(b"hello world")
        assert h.startswith("sha256:")
        assert len(h) == 71  # "sha256:" + 64 hex chars

    def test_hash_deterministic(self):
        h1 = compute_content_hash(b"test content")
        h2 = compute_content_hash(b"test content")
        assert h1 == h2

    def test_hash_different_content(self):
        h1 = compute_content_hash(b"content a")
        h2 = compute_content_hash(b"content b")
        assert h1 != h2

    def test_hash_file(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_bytes(b"file content")
        h_file = compute_content_hash(f.read_bytes())
        h_direct = compute_content_hash(b"file content")
        assert h_file == h_direct


class TestAtomicWrite:
    def test_write_creates_file(self, tmp_path):
        target = tmp_path / "output.md"
        atomic_write(target, b"hello")
        assert target.read_bytes() == b"hello"

    def test_write_creates_parent_dirs(self, tmp_path):
        target = tmp_path / "a" / "b" / "c" / "file.md"
        atomic_write(target, b"nested")
        assert target.read_bytes() == b"nested"

    def test_write_overwrites_existing(self, tmp_path):
        target = tmp_path / "file.md"
        target.write_bytes(b"old")
        atomic_write(target, b"new")
        assert target.read_bytes() == b"new"

    def test_no_temp_files_left(self, tmp_path):
        target = tmp_path / "file.md"
        atomic_write(target, b"content")
        files = list(tmp_path.iterdir())
        assert len(files) == 1
        assert files[0].name == "file.md"


class TestManifest:
    def test_read_nonexistent_returns_empty(self, tmp_path):
        result = read_manifest(tmp_path / "missing.yaml")
        assert result == {}

    def test_write_and_read_roundtrip(self, tmp_path):
        manifest_path = tmp_path / "manifest.yaml"
        data = {
            "document_uid": "doc_abc123",
            "canonical_path": "docs/requirements/auth.md",
            "branches": {
                "main": {
                    "head": "v001",
                    "versions": [
                        {"version": 1, "file": "main/v001.md", "content_hash": "sha256:aaa"}
                    ],
                }
            },
        }
        write_manifest(manifest_path, data)
        result = read_manifest(manifest_path)
        assert result == data

    def test_write_is_atomic(self, tmp_path):
        """No temp files left after write."""
        manifest_path = tmp_path / "manifest.yaml"
        write_manifest(manifest_path, {"key": "value"})
        files = list(tmp_path.iterdir())
        assert len(files) == 1
        assert files[0].name == "manifest.yaml"
