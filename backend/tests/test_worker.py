from pathlib import Path
from uuid import uuid4

import pytest

from datum.models.core import Document, DocumentVersion, Project
from datum.models.search import IngestionJob
from datum.worker import process_job


class _FakeSession:
    def __init__(self, objects=None):
        self._objects = objects or {}
        self.commit_calls = 0

    async def get(self, model, key):
        return self._objects.get((model, key))

    async def commit(self):
        self.commit_calls += 1


@pytest.mark.asyncio
async def test_process_job_persists_skipped_terminal_state(monkeypatch, tmp_path: Path):
    version_id = uuid4()
    document_id = uuid4()
    project_id = uuid4()
    job = IngestionJob(
        id=uuid4(),
        project_id=project_id,
        version_id=version_id,
        job_type="embed",
        status="queued",
    )
    version = DocumentVersion(
        id=version_id,
        document_id=document_id,
        version_number=1,
        branch="main",
        content_hash="sha256:test",
        filesystem_path=str(tmp_path / "docs/test.md"),
    )
    document = Document(
        id=document_id,
        project_id=project_id,
        uid="doc_test",
        slug="test",
        canonical_path="docs/test.md",
        title="Test",
        doc_type="plan",
    )
    project = Project(
        id=project_id,
        uid="proj_test",
        slug="test",
        name="Test",
        filesystem_path=str(tmp_path),
        project_yaml_hash="sha256:project",
    )
    session = _FakeSession(
        {
            (DocumentVersion, version_id): version,
            (Document, document_id): document,
            (Project, project_id): project,
        }
    )

    async def fake_handle_embed_job(session, job, version, gateway):
        job.status = "skipped"
        job.error_message = "embedding gateway unavailable"

    monkeypatch.setattr("datum.worker._handle_embed_job", fake_handle_embed_job)

    await process_job(session, job, gateway=object())

    assert job.status == "skipped"
    assert job.completed_at is not None
    assert session.commit_calls == 2
