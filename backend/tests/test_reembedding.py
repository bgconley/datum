from uuid import uuid4

import pytest

from datum.models.core import Document, DocumentVersion, ModelRun
from datum.models.search import IngestionJob
from datum.services.reembedding import (
    ReembeddingPlan,
    drop_embeddings,
    get_embedding_stats,
    plan_reembedding,
    start_reembedding,
)


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        return self

    def all(self):
        return self._value

    def fetchall(self):
        return self._value


class _ReembedSession:
    def __init__(self):
        self.added = []
        self.version_ids = []
        self.versions = {}
        self.documents = {}
        self.execute_calls = []
        self.committed = False

    async def execute(self, statement, params=None):
        rendered = str(statement)
        self.execute_calls.append((rendered, params or {}))
        if "count(" in rendered:
            return _ScalarResult(len(self.version_ids))
        if "SELECT DISTINCT document_chunks.version_id" in rendered:
            return _ScalarResult(self.version_ids)
        if "FROM ingestion_jobs" in rendered:
            return _ScalarResult(None)
        if "FROM model_runs" in rendered:
            return _ScalarResult([])
        return _ScalarResult([])

    async def get(self, model, key):
        if model is DocumentVersion:
            return self.versions.get(key)
        if model is Document:
            return self.documents.get(key)
        return None

    def add(self, obj):
        if isinstance(obj, ModelRun) and obj.id is None:
            obj.id = uuid4()
        self.added.append(obj)

    async def flush(self):
        return None

    async def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_plan_reembedding_counts_chunks():
    session = _ReembedSession()
    session.version_ids = [uuid4(), uuid4(), uuid4()]

    plan = await plan_reembedding(session, "Qwen3-Embedding-4B", batch_size=2)

    assert isinstance(plan, ReembeddingPlan)
    assert plan.total_chunks == 3
    assert plan.estimated_batches == 2


@pytest.mark.asyncio
async def test_start_reembedding_queues_embed_jobs():
    session = _ReembedSession()
    version_id = uuid4()
    document_id = uuid4()
    project_id = uuid4()
    session.version_ids = [version_id]
    session.versions[version_id] = DocumentVersion(
        id=version_id,
        document_id=document_id,
        version_number=1,
        branch="main",
        content_hash="sha256:test",
        filesystem_path="/tmp/docs/test.md",
    )
    session.documents[document_id] = Document(
        id=document_id,
        project_id=project_id,
        uid="doc_test",
        slug="test",
        canonical_path="docs/test.md",
        title="Test",
        doc_type="plan",
    )

    run_id = await start_reembedding(session, "Qwen3-Embedding-4B")

    assert run_id is not None
    jobs = [obj for obj in session.added if isinstance(obj, IngestionJob)]
    assert len(jobs) == 1
    assert jobs[0].job_type == "embed"
    assert jobs[0].model_run_id == run_id
    assert session.committed is True


@pytest.mark.asyncio
async def test_get_embedding_stats_returns_rows():
    session = _ReembedSession()
    session.execute_calls = []

    async def execute(statement, params=None):
        session.execute_calls.append((str(statement), params or {}))
        return _ScalarResult(
            [
                ("Qwen3-Embedding-4B", "run-1", 5, None, None),
            ]
        )

    session.execute = execute  # type: ignore[method-assign]
    stats = await get_embedding_stats(session)
    assert stats[0]["model_name"] == "Qwen3-Embedding-4B"
    assert stats[0]["embedding_count"] == 5


@pytest.mark.asyncio
async def test_drop_embeddings_returns_deleted_count():
    session = _ReembedSession()

    calls = {"count": 0}

    async def execute(statement, params=None):
        calls["count"] += 1
        if calls["count"] == 1:
            return _ScalarResult(3)
        return _ScalarResult([])

    session.execute = execute  # type: ignore[method-assign]
    deleted = await drop_embeddings(session, uuid4())
    assert deleted == 3
