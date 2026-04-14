from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from datum.models.core import Document, DocumentVersion, Project
from datum.models.intelligence import EntityRelationship
from datum.models.search import ChunkEmbedding, DocumentChunk, IngestionJob, VersionText
from datum.services.chunking import Chunk
from datum.worker import (
    _handle_chunk_job,
    _handle_embed_job,
    _handle_extract_job,
    _handle_relationship_job,
    _handle_schema_parse_job,
    process_job,
)


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


class _RowResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


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


class _ExtractJobSession:
    def __init__(self):
        self.executed_statements: list[str] = []
        self.added = []

    async def execute(self, statement, params=None):
        del params
        self.executed_statements.append(str(statement))
        return _ScalarOneResult(None)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        return None


class _SchemaParseSession:
    def __init__(self, document: Document, chunks: list[DocumentChunk]):
        self.document = document
        self.chunks = chunks
        self.executed_statements: list[str] = []
        self.added = []

    async def get(self, model, key):
        if model is Document and key == self.document.id:
            return self.document
        return None

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


class _RelationshipJobSession:
    def __init__(self, chunks: list[DocumentChunk], mentions: list[tuple[object, object]]):
        self.chunks = chunks
        self.mentions = mentions
        self.executed_statements: list[str] = []
        self.added = []

    async def execute(self, statement, params=None):
        del params
        rendered = str(statement)
        self.executed_statements.append(rendered)
        if "FROM document_chunks" in rendered:
            return _ScalarListResult(self.chunks)
        if "FROM entity_mentions" in rendered:
            return _RowResult(self.mentions)
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
async def test_schema_parse_job_persists_relationship_evidence_spans(monkeypatch):
    version_id = uuid4()
    document = Document(
        id=uuid4(),
        project_id=uuid4(),
        uid="doc_schema",
        slug="schema",
        canonical_path="docs/schema.sql",
        title="Schema",
        doc_type="reference",
    )
    version = DocumentVersion(
        id=version_id,
        document_id=document.id,
        version_number=1,
        branch="main",
        content_hash="sha256:schema",
        filesystem_path="/tmp/docs/schema.sql",
    )
    version_text = VersionText(
        version_id=version_id,
        text_kind="raw",
        content="CREATE TABLE sessions (\n  user_id uuid REFERENCES users(id)\n);\n",
        content_hash="sha256:text",
    )
    chunk = DocumentChunk(
        id=uuid4(),
        version_id=version_id,
        chunk_index=0,
        content=version_text.content,
        heading_path=["Schema"],
        start_char=0,
        end_char=len(version_text.content),
        token_count=10,
        content_hash="sha256:chunk",
        source_text_hash="sha256:text",
    )
    session = _SchemaParseSession(document=document, chunks=[chunk])
    job = IngestionJob(
        id=uuid4(),
        project_id=document.project_id,
        version_id=version_id,
        job_type="schema_parse",
        status="queued",
    )

    async def fake_load_latest_version_text(session, version_id):
        del session, version_id
        return version_text

    async def fake_get_or_create_entity(session, entity_type, canonical_name, metadata=None):
        del session, metadata
        return SimpleNamespace(id=uuid4(), entity_type=entity_type, canonical_name=canonical_name)

    monkeypatch.setattr("datum.worker._load_latest_version_text", fake_load_latest_version_text)
    monkeypatch.setattr("datum.worker._get_or_create_entity", fake_get_or_create_entity)
    monkeypatch.setattr(
        "datum.worker.extract_schema_intelligence",
        lambda content, suffix: (
            [
                SimpleNamespace(
                    name="sessions.user_id",
                    entity_type="column",
                    properties={},
                ),
                SimpleNamespace(
                    name="users.id",
                    entity_type="column",
                    properties={},
                ),
            ],
            [
                SimpleNamespace(
                    source="sessions.user_id",
                    target="users.id",
                    relationship_type="foreign_key",
                    evidence_text="user_id uuid REFERENCES users(id)",
                )
            ],
        ),
    )

    await _handle_schema_parse_job(session, job, version)

    persisted = [obj for obj in session.added if isinstance(obj, EntityRelationship)]
    assert len(persisted) == 1
    assert persisted[0].evidence_chunk_id == chunk.id
    assert persisted[0].evidence_start_char is not None
    assert persisted[0].evidence_end_char is not None
    assert persisted[0].evidence_text == "user_id uuid REFERENCES users(id)"


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
async def test_relationship_job_persists_chunk_span_metadata(monkeypatch):
    version_id = uuid4()
    chunk = DocumentChunk(
        id=uuid4(),
        version_id=version_id,
        chunk_index=0,
        content="Auth service writes to PostgreSQL for session state.",
        heading_path=["Storage"],
        start_char=100,
        end_char=152,
        token_count=10,
        content_hash="sha256:chunk",
        source_text_hash="sha256:text",
    )
    source_entity = SimpleNamespace(id=uuid4(), canonical_name="auth service")
    target_entity = SimpleNamespace(id=uuid4(), canonical_name="postgresql")
    mentions = [
        (SimpleNamespace(chunk_id=chunk.id), source_entity),
        (SimpleNamespace(chunk_id=chunk.id), target_entity),
    ]
    session = _RelationshipJobSession([chunk], mentions)
    job = IngestionJob(
        id=uuid4(),
        project_id=uuid4(),
        version_id=version_id,
        job_type="relate_llm",
        status="queued",
    )
    version = DocumentVersion(
        id=version_id,
        document_id=uuid4(),
        version_number=1,
        branch="main",
        content_hash="sha256:test",
        filesystem_path="/tmp/docs/architecture.md",
    )

    async def fake_extract_relationships_llm(content, names, gateway):
        del content, names, gateway
        return [
            SimpleNamespace(
                source_entity="auth service",
                target_entity="postgresql",
                relationship_type="uses",
                evidence_text="writes to PostgreSQL",
                confidence=0.83,
            )
        ]

    async def fake_model_run(session, job, gateway):
        del session, job, gateway
        return SimpleNamespace(id=uuid4(), items_processed=0)

    class _Gateway:
        llm = object()

        async def check_health(self, model_type):
            assert model_type == "llm"
            return True

    monkeypatch.setattr("datum.worker.extract_relationships_llm", fake_extract_relationships_llm)
    monkeypatch.setattr("datum.worker._resolve_llm_model_run", fake_model_run)

    await _handle_relationship_job(session, job, version, gateway=_Gateway())

    persisted = [obj for obj in session.added if isinstance(obj, EntityRelationship)]
    assert len(persisted) == 1
    assert persisted[0].evidence_chunk_id == chunk.id
    assert persisted[0].evidence_start_char == chunk.start_char + chunk.content.index(
        "writes to PostgreSQL"
    )
    assert persisted[0].evidence_end_char == persisted[0].evidence_start_char + len(
        "writes to PostgreSQL"
    )


@pytest.mark.asyncio
async def test_extract_job_queues_candidate_and_ner_stages(monkeypatch, tmp_path: Path):
    version = DocumentVersion(
        id=uuid4(),
        document_id=uuid4(),
        version_number=1,
        branch="main",
        content_hash="sha256:test",
        filesystem_path=str(tmp_path / "docs/adr.md"),
    )
    job = IngestionJob(
        id=uuid4(),
        project_id=uuid4(),
        version_id=version.id,
        job_type="extract",
        status="queued",
    )
    session = _ExtractJobSession()
    queued_job_types: list[str] = []

    async def fake_run_extraction_async(ctx):
        del ctx
        return type(
            "ExtractionResult",
            (),
            {
                "text_kind": "raw",
                "content": "# ADR\n\n## Decision\nUse ParadeDB.",
                "content_hash": "sha256:content",
            },
        )()

    async def fake_queue_job(session, **kwargs):
        del session
        queued_job_types.append(kwargs["job_type"])

    async def fake_chunking_config(*args, **kwargs):
        del args, kwargs
        return type("Config", (), {"id": uuid4(), "config_hash": "chunk-config"})()

    async def fake_candidate_config(*args, **kwargs):
        del args, kwargs
        return type("Config", (), {"id": uuid4(), "config_hash": "candidate-config"})()

    async def fake_ner_config(*args, **kwargs):
        del args, kwargs
        return type("Config", (), {"id": uuid4(), "config_hash": "ner-config"})()

    monkeypatch.setattr("datum.worker.run_extraction_async", fake_run_extraction_async)
    monkeypatch.setattr("datum.worker._queue_job", fake_queue_job)
    monkeypatch.setattr("datum.worker.get_chunking_pipeline_config", fake_chunking_config)
    monkeypatch.setattr(
        "datum.worker.get_candidate_extraction_pipeline_config",
        fake_candidate_config,
    )
    monkeypatch.setattr("datum.worker.get_ner_pipeline_config", fake_ner_config)

    await _handle_extract_job(
        session,
        job,
        version,
        ctx=type("Ctx", (), {"project_path": tmp_path, "canonical_path": "docs/adr.md"})(),
        gateway=type("Gateway", (), {"ner": object()})(),
    )

    assert isinstance(session.added[0], VersionText)
    assert queued_job_types == ["chunk", "extract_candidates", "ner_gliner", "link_detect"]


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
