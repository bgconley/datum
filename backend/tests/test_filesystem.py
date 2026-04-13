
import pytest

from datum.services.filesystem import (
    atomic_write,
    compute_content_hash,
    doc_manifest_dir,
    read_manifest,
    validate_canonical_path,
    write_manifest,
)


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


class TestPathValidation:
    def test_valid_relative_path(self):
        result = validate_canonical_path("docs/requirements/auth.md")
        assert str(result) == "docs/requirements/auth.md"

    def test_rejects_absolute_path(self):
        with pytest.raises(ValueError, match="must be relative"):
            validate_canonical_path("/etc/passwd")

    def test_rejects_parent_traversal(self):
        with pytest.raises(ValueError, match="escapes project boundary"):
            validate_canonical_path("../escape.md")

    def test_rejects_nested_traversal(self):
        with pytest.raises(ValueError, match="escapes project boundary"):
            validate_canonical_path("docs/../../escape.md")

    def test_normalizes_inner_dots(self):
        result = validate_canonical_path("docs/./requirements/auth.md")
        assert str(result) == "docs/requirements/auth.md"

    def test_doc_manifest_dir_valid(self, tmp_path):
        result = doc_manifest_dir(tmp_path, "docs/requirements/auth-req.md")
        expected = tmp_path / ".piq" / "docs" / "requirements" / "auth-req.md"
        assert result == expected

    def test_doc_manifest_dir_rejects_traversal(self, tmp_path):
        with pytest.raises(ValueError):
            doc_manifest_dir(tmp_path, "../escape.md")

    def test_doc_manifest_dir_rejects_absolute(self, tmp_path):
        with pytest.raises(ValueError):
            doc_manifest_dir(tmp_path, "/etc/passwd")

    def test_same_stem_different_extension_separate_manifests(self, tmp_path):
        """Blocker regression: foo.md and foo.sql must have separate manifest dirs."""
        dir_md = doc_manifest_dir(tmp_path, "docs/foo.md")
        dir_sql = doc_manifest_dir(tmp_path, "docs/foo.sql")
        assert dir_md != dir_sql
        assert dir_md.name == "foo.md"
        assert dir_sql.name == "foo.sql"
