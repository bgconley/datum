import pytest
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from datum.services.project_manager import create_project
from datum.services.watcher_utils import should_process_path, compute_file_state, FileState


class TestShouldProcessPath:
    def test_ignores_piq(self):
        assert not should_process_path(Path("/projects/my-proj/.piq/manifest.yaml"))

    def test_ignores_tmp(self):
        assert not should_process_path(Path("/projects/my-proj/.file.tmp"))

    def test_ignores_swp(self):
        assert not should_process_path(Path("/projects/my-proj/.file.swp"))

    def test_ignores_ds_store(self):
        assert not should_process_path(Path("/projects/my-proj/.DS_Store"))

    def test_accepts_doc(self):
        assert should_process_path(Path("/projects/my-proj/docs/notes.md"))

    def test_accepts_attachment_metadata(self):
        assert should_process_path(Path("/projects/my-proj/attachments/a/metadata.yaml"))

    def test_accepts_project_yaml(self):
        assert should_process_path(Path("/projects/my-proj/project.yaml"))


class TestComputeFileState:
    def test_returns_state(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_bytes(b"hello")
        state = compute_file_state(f)
        assert state is not None
        assert state.content_hash.startswith("sha256:")
        assert state.byte_size == 5

    def test_missing_file_returns_none(self, tmp_path):
        state = compute_file_state(tmp_path / "missing.md")
        assert state is None
