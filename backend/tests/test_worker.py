from pathlib import Path
from uuid import uuid4

import pytest

from datum.models.core import Document, DocumentVersion, Project
from datum.models.search import ChunkEmbedding, DocumentChunk, IngestionJob, VersionText
from datum.services.chunking import Chunk
from datum.worker import _handle_chunk_job, _handle_embed_job, process_job


class _FakeSession:
    def __init__(self, objects=None):
        self._objects = objects or {}
        self.commit_calls = 0

    async def get(self, model, key):
        return self._objects.get((model, key))

    async def commit(self):
        self.commit_calls += 1


class _ScalarOneResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _ScalarListResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return self

    def all(self):
        return self._values


class _ChunkJobSession:
    def __init__(self, version_text: VersionText, existing_chunk_ids: list[str]):
        self.version_text = version_text
        self.existing_chunk_ids = existing_chunk_ids
        self.executed_statements: list[str] = []
        self.added = []

    async def execute(self, statement, params=None):
        rendered = str(statement)
        self.executed_statements.append(rendered)
        if "FROM version_texts" in rendered:
            return _ScalarOneResult(self.version_text)
        if "SELECT document_chunks.id" in rendered:
            return _ScalarListResult(self.existing_chunk_ids)
        return _ScalarOneResult(None)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        return None


class _EmbedJobSession:
    def __init__(self, chunks: list[DocumentChunk]):
        self.chunks = chunks
        self.executed_statements: list[str] = []
        self.added = []

    async def execute(self, statement, params=None):
        del params
        rendered = str(statement)
        self.executed_statements.append(rendered)
        if "FROM document_chunks" in rendered:
            return _ScalarListResult(self.chunks)
        return _ScalarOneResult(None)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        return None


class _FailureSession:
    def __init__(self, objects=None):
        self._objects = objects or {}
        self.commit_calls = 0
        self.rollback_calls = 0

    async def get(self, model, key):
        return self._objects.get((model, key))

    async def commit(self):
        self.commit_calls += 1

    async def rollback(self):
        self.rollback_calls += 1


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


@pytest.mark.asyncio
async def test_chunk_job_deletes_dependents_before_replacing_chunks(monkeypatch):
    version_id = uuid4()
    project_id = uuid4()
    version_text = VersionText(
        version_id=version_id,
        text_kind="raw",
        content="# Title\n\nBody",
        content_hash="sha256:text",
    )
    session = _ChunkJobSession(version_text=version_text, existing_chunk_ids=[uuid4()])
    job = IngestionJob(
        id=uuid4(),
        project_id=project_id,
        version_id=version_id,
        job_type="chunk",
        status="queued",
    )
    version = DocumentVersion(
        id=version_id,
        document_id=uuid4(),
        version_number=1,
        branch="main",
        content_hash="sha256:test",
        filesystem_path="/tmp/docs/test.md",
    )

    async def fake_queue_job(*args, **kwargs):
        return None

    async def fake_chunking_config(*args, **kwargs):
        return type("Config", (), {"id": uuid4(), "config_hash": "chunk-config"})()

    async def fake_terms_config(*args, **kwargs):
        return type("Config", (), {"id": uuid4(), "config_hash": "terms-config"})()

    async def fake_embedding_config(*args, **kwargs):
        return type("Config", (), {"id": uuid4(), "config_hash": "embed-config"})()

    async def fake_model_run(*args, **kwargs):
        return type("ModelRun", (), {"id": uuid4()})()

    monkeypatch.setattr(
        "datum.worker.run_chunking",
        lambda content: [
            Chunk(
                content="Body",
                heading_path=["Title"],
                start_char=0,
                end_char=4,
                start_line=1,
                end_line=2,
                token_count=1,
                chunk_index=0,
            )
        ],
    )
    monkeypatch.setattr("datum.worker.get_chunking_pipeline_config", fake_chunking_config)
    monkeypatch.setattr("datum.worker.get_technical_terms_pipeline_config", fake_terms_config)
    monkeypatch.setattr("datum.worker.get_embedding_pipeline_config", fake_embedding_config)
    monkeypatch.setattr("datum.worker.get_active_embedding_model_run", fake_model_run)
    monkeypatch.setattr("datum.worker._queue_job", fake_queue_job)

    await _handle_chunk_job(session, job, version, gateway=object())

    delete_embeddings_index = next(
        index
        for index, statement in enumerate(session.executed_statements)
        if "DELETE FROM chunk_embeddings" in statement
    )
    delete_terms_index = next(
        index
        for index, statement in enumerate(session.executed_statements)
        if "DELETE FROM technical_terms" in statement
    )
    delete_chunks_index = next(
        index
        for index, statement in enumerate(session.executed_statements)
        if "DELETE FROM document_chunks" in statement
    )

    assert delete_embeddings_index < delete_chunks_index
    assert delete_terms_index < delete_chunks_index


@pytest.mark.asyncio
async def test_embed_job_persists_typed_chunk_embeddings(monkeypatch):
    version_id = uuid4()
    model_run_id = uuid4()
    chunk = DocumentChunk(
        id=uuid4(),
        version_id=version_id,
        chunk_index=0,
        content="Body",
        heading_path=["Title"],
        start_char=0,
        end_char=4,
        token_count=1,
        content_hash="sha256:chunk",
        source_text_hash="sha256:text",
    )
    session = _EmbedJobSession([chunk])
    job = IngestionJob(
        id=uuid4(),
        project_id=uuid4(),
        version_id=version_id,
        job_type="embed",
        status="queued",
    )
    version = DocumentVersion(
        id=version_id,
        document_id=uuid4(),
        version_number=1,
        branch="main",
        content_hash="sha256:test",
        filesystem_path="/tmp/docs/test.md",
    )

    async def fake_run_embedding(chunks, gateway):
        del chunks, gateway
        return [[0.1] * 1024]

    async def fake_model_run(session, job, gateway):
        del session, job, gateway
        return type("ModelRun", (), {"id": model_run_id, "items_processed": 0})()

    monkeypatch.setattr("datum.worker.run_embedding", fake_run_embedding)
    monkeypatch.setattr("datum.worker._resolve_embedding_model_run", fake_model_run)

    class _Gateway:
        embedding = object()

        async def check_health(self, model_type):
            assert model_type == "embedding"
            return True

    gateway = _Gateway()
    await _handle_embed_job(session, job, version, gateway=gateway)

    persisted = [obj for obj in session.added if isinstance(obj, ChunkEmbedding)]
    assert len(persisted) == 1
    assert persisted[0].chunk_id == chunk.id
    assert persisted[0].model_run_id == model_run_id
    assert len(persisted[0].embedding) == 1024
    assert all("INSERT INTO chunk_embeddings" not in stmt for stmt in session.executed_statements)


@pytest.mark.asyncio
async def test_process_job_rolls_back_before_persisting_failure(monkeypatch, tmp_path: Path):
    version_id = uuid4()
    document_id = uuid4()
    project_id = uuid4()
    job_id = uuid4()
    job = IngestionJob(
        id=job_id,
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
    session = _FailureSession(
        {
            (IngestionJob, job_id): job,
            (DocumentVersion, version_id): version,
            (Document, document_id): document,
            (Project, project_id): project,
        }
    )

    async def fake_handle_embed_job(session, job, version, gateway):
        del session, job, version, gateway
        raise RuntimeError("boom")

    monkeypatch.setattr("datum.worker._handle_embed_job", fake_handle_embed_job)

    await process_job(session, job, gateway=object())

    assert session.rollback_calls == 1
    assert session.commit_calls == 2
    assert job.status == "failed"
    assert job.error_message == "boom"
    assert job.completed_at is not None
