from uuid import uuid4

import pytest

from datum.models.search import SearchRun, SearchRunResult
from datum.services.search import (
    FusedResult,
    ParsedQuery,
    RankedCandidate,
    SearchOptions,
    SearchResult,
    SearchResultEntity,
    _build_entity_facets,
    _log_search_run,
    _prepare_search_context,
    _term_search,
    _vector_search,
    fuse_results,
    parse_query,
)
from datum.services.technical_terms import TermMatch


class _FakeExecuteResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeSession:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.executed = []
        self.added = []
        self.committed = False
        self.rolled_back = False

    async def execute(self, statement, params=None):
        self.executed.append((statement, params or {}))
        return _FakeExecuteResult(self.rows)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        for obj in self.added:
            if isinstance(obj, SearchRun) and obj.id is None:
                obj.id = uuid4()

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True


class TestParseQuery:
    def test_basic_query(self):
        parsed = parse_query("JWT token lifetime")
        assert isinstance(parsed, ParsedQuery)
        assert parsed.bm25_query == "JWT token lifetime"

    def test_detects_version_numbers(self):
        parsed = parse_query("upgrade to v3.0.0")
        assert any(term.term_type == "version" for term in parsed.detected_terms)

    def test_detects_env_vars(self):
        parsed = parse_query("set DATABASE_URL to postgres")
        assert any(term.term_type == "env_var" for term in parsed.detected_terms)

    def test_detects_api_routes(self):
        parsed = parse_query("GET /api/v1/users endpoint")
        assert any(term.term_type == "api_route" for term in parsed.detected_terms)


class TestFuseResults:
    def test_rrf_combines_signals(self):
        bm25 = [RankedCandidate(chunk_id="a", rank=1), RankedCandidate(chunk_id="b", rank=2)]
        vector = [RankedCandidate(chunk_id="b", rank=1), RankedCandidate(chunk_id="c", rank=2)]
        fused = fuse_results(bm25_results=bm25, vector_results=vector)
        assert fused[0].chunk_id == "b"

    def test_rrf_handles_empty(self):
        assert fuse_results(bm25_results=[], vector_results=[]) == []

    def test_rrf_deduplicates(self):
        bm25 = [RankedCandidate(chunk_id="a", rank=1)]
        vector = [RankedCandidate(chunk_id="a", rank=1)]
        fused = fuse_results(bm25_results=bm25, vector_results=vector)
        assert len(fused) == 1


def test_build_entity_facets_counts_unique_result_entities():
    facets = _build_entity_facets(
        [
            SearchResult(
                document_title="A",
                document_path="docs/a.md",
                document_type="plan",
                document_status="draft",
                project_slug="p",
                heading_path="",
                snippet="",
                version_number=1,
                content_hash="sha256:a",
                fused_score=1.0,
                entities=[
                    SearchResultEntity(canonical_name="postgresql", entity_type="technology"),
                    SearchResultEntity(canonical_name="redis", entity_type="technology"),
                ],
            ),
            SearchResult(
                document_title="B",
                document_path="docs/b.md",
                document_type="plan",
                document_status="draft",
                project_slug="p",
                heading_path="",
                snippet="",
                version_number=1,
                content_hash="sha256:b",
                fused_score=0.9,
                entities=[
                    SearchResultEntity(canonical_name="postgresql", entity_type="technology"),
                ],
            ),
        ]
    )

    assert [(facet.canonical_name, facet.count) for facet in facets] == [
        ("postgresql", 2),
        ("redis", 1),
    ]


@pytest.mark.asyncio
async def test_vector_search_scopes_to_active_model_run():
    session = _FakeSession()
    model_run_id = uuid4()

    results = await _vector_search(
        session,
        query_embedding=[0.1] * 1024,
        embedding_model_run_id=model_run_id,
        version_scope="current",
        project_scope="alpha",
        limit=10,
    )

    assert results == []
    statement, params = session.executed[0]
    rendered = str(statement)
    assert "chunk_embeddings.model_run_id" in rendered
    assert "projects.slug" in rendered
    assert "CAST(:embedding AS halfvec" not in rendered
    assert params == {}


@pytest.mark.asyncio
async def test_prepare_search_context_resolves_active_reranker_model_run(monkeypatch):
    retrieval_config_id = uuid4()
    reranker_run_id = uuid4()
    session = _FakeSession()

    async def fake_retrieval_config(session, search_options):
        del session, search_options
        return type("Config", (), {"id": retrieval_config_id, "config": {}})()

    async def fake_reranker_run(session, gateway, create):
        del session, gateway
        assert create is True
        return type("ModelRun", (), {"id": reranker_run_id})()

    monkeypatch.setattr("datum.services.search._resolve_retrieval_config", fake_retrieval_config)
    monkeypatch.setattr("datum.services.search.get_active_reranker_model_run", fake_reranker_run)

    class _Gateway:
        embedding = None
        reranker = object()

    context = await _prepare_search_context(
        session,
        query="DATABASE_URL",
        gateway=_Gateway(),
        project_scope="alpha",
        version_scope="current",
        search_options=SearchOptions(),
    )

    assert context.retrieval_config_id == retrieval_config_id
    assert context.reranker_enabled is True
    assert context.reranker_model_run_id == reranker_run_id


@pytest.mark.asyncio
async def test_vector_search_skips_dimension_mismatch():
    session = _FakeSession()
    model_run_id = uuid4()

    results = await _vector_search(
        session,
        query_embedding=[0.1, 0.2, 0.3],
        embedding_model_run_id=model_run_id,
        version_scope="current",
        project_scope="alpha",
        limit=10,
    )

    assert results == []
    assert session.executed == []


@pytest.mark.asyncio
async def test_term_search_applies_as_of_scope():
    session = _FakeSession()

    results = await _term_search(
        session,
        ParsedQuery(
            raw="DATABASE_URL",
            bm25_query="DATABASE_URL",
            detected_terms=[
                TermMatch(
                    raw_text="DATABASE_URL",
                    normalized_text="database_url",
                    term_type="env_var",
                    start_char=0,
                    end_char=12,
                    confidence=1.0,
                )
            ],
            version_scope="as_of:2026-01-01T00:00:00+00:00",
            project_scope="alpha",
        ),
        version_scope="as_of:2026-01-01T00:00:00+00:00",
        limit=10,
    )

    assert results == []
    statement, _ = session.executed[0]
    rendered = str(statement)
    assert "version_head_events" in rendered
    assert "valid_from" in rendered
    assert "projects.slug" in rendered


@pytest.mark.asyncio
async def test_log_search_run_persists_config_references():
    session = _FakeSession()
    retrieval_config_id = uuid4()
    embedding_model_run_id = uuid4()
    reranker_model_run_id = uuid4()

    await _log_search_run(
        session=session,
        query="DATABASE_URL",
        parsed=ParsedQuery(
            raw="DATABASE_URL",
            bm25_query="DATABASE_URL",
            detected_terms=[],
            version_scope="all",
            project_scope="alpha",
        ),
        retrieval_config_id=retrieval_config_id,
        embedding_model_run_id=embedding_model_run_id,
        reranker_model_run_id=reranker_model_run_id,
        version_scope="all",
        project_scope="alpha",
        elapsed_ms=12,
        fused_results=[
            FusedResult(
                chunk_id=str(uuid4()),
                fused_score=1.0,
                rank_bm25=1,
                rerank_score=0.7,
            )
        ],
        results=[],
    )

    search_run = next(obj for obj in session.added if isinstance(obj, SearchRun))
    search_run_result = next(obj for obj in session.added if isinstance(obj, SearchRunResult))

    assert search_run.retrieval_config_id == retrieval_config_id
    assert search_run.embedding_model_run_id == embedding_model_run_id
    assert search_run.reranker_model_run_id == reranker_model_run_id
    assert search_run.parsed_query["version_scope"] == "all"
    assert search_run_result.search_run_id == search_run.id
    assert search_run_result.rerank_score == 0.7
    assert session.committed is True
