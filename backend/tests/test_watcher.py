from pathlib import Path

from datum.services.watcher_utils import compute_file_state, should_process_path


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


class TestDebouncedHandlerRename:
    """Finding 1: watcher must handle editor atomic-save rename flows."""

    def test_move_event_records_dest_path(self, tmp_path):
        from datum.watcher import DebouncedHandler
        handler = DebouncedHandler(tmp_path)

        # Simulate a FileMovedEvent where src is a temp file (filtered) and dest is real
        class FakeMovedEvent:
            is_directory = False
            src_path = str(tmp_path / ".note.md.tmp")
            dest_path = str(tmp_path / "proj" / "docs" / "note.md")
            event_type = "moved"

        handler.on_any_event(FakeMovedEvent())

        # dest_path should be in _pending even though src_path was filtered
        assert str(tmp_path / "proj" / "docs" / "note.md") in handler._pending

    def test_regular_event_still_works(self, tmp_path):
        from datum.watcher import DebouncedHandler
        handler = DebouncedHandler(tmp_path)

        class FakeModifiedEvent:
            is_directory = False
            src_path = str(tmp_path / "proj" / "docs" / "file.md")
            event_type = "modified"

        handler.on_any_event(FakeModifiedEvent())
        assert str(tmp_path / "proj" / "docs" / "file.md") in handler._pending
