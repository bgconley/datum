"""Hybrid search with BM25, vectors, and technical terms."""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from uuid import UUID

import yaml
from sqlalchemy import and_, false, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from datum.config import settings
from datum.models.core import Document, DocumentVersion, PipelineConfig, Project, VersionHeadEvent
from datum.models.intelligence import Entity, EntityMention
from datum.models.search import (
    ChunkEmbedding,
    DocumentChunk,
    SearchRun,
    SearchRunResult,
    TechnicalTerm,
)
from datum.services.filesystem import read_manifest, resolve_manifest_dir
from datum.services.pipeline_configs import (
    RETRIEVAL_RRF_K,
    RETRIEVAL_WEIGHTS,
    get_active_embedding_model_run,
    get_active_reranker_model_run,
    get_retrieval_pipeline_config,
)
from datum.services.technical_terms import TermMatch, extract_technical_terms

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ParsedQuery:
    raw: str
    bm25_query: str
    detected_terms: list[TermMatch] = field(default_factory=list)
    version_scope: str = "current"
    project_scope: str | None = None


@dataclass(slots=True)
class RankedCandidate:
    chunk_id: str
    rank: int
    score: float = 0.0


@dataclass(slots=True)
class FusedResult:
    chunk_id: str
    fused_score: float
    rank_bm25: int | None = None
    rank_vector: int | None = None
    rank_terms: int | None = None
    rerank_score: float | None = None


@dataclass(slots=True)
class SearchResult:
    document_title: str
    document_path: str
    document_type: str
    document_status: str
    project_slug: str
    heading_path: str
    snippet: str
    version_number: int
    content_hash: str
    fused_score: float
    matched_terms: list[str] = field(default_factory=list)
    document_uid: str = ""
    chunk_id: str = ""
    line_start: int = 0
    line_end: int = 0
    match_signals: list[str] = field(default_factory=list)
    entities: list[SearchResultEntity] = field(default_factory=list)


@dataclass(slots=True)
class SearchResultEntity:
    canonical_name: str
    entity_type: str


@dataclass(slots=True)
class SearchEntityFacet:
    canonical_name: str
    entity_type: str
    count: int


@dataclass(slots=True)
class SearchExecutionContext:
    query: str
    parsed: ParsedQuery
    resolved_scope: ResolvedVersionScope
    retrieval_config_id: UUID | None
    active_embedding_run_id: UUID | None
    semantic_enabled: bool
    reranker_enabled: bool
    reranker_model_run_id: UUID | None
    rrf_k: int
    weight_bm25: float
    weight_vector: float
    weight_terms: float


@dataclass(slots=True)
class SearchOptions:
    retrieval_config_id: UUID | None = None
    embedding_model_run_id: UUID | None = None
    reranker_enabled: bool | None = None
    reranker_model_run_id: UUID | None = None
    rerank_candidate_limit: int = 50
    max_results_per_document: int | None = 3
    allowed_document_types: tuple[str, ...] | None = None


@dataclass(slots=True)
class SearchExecution:
    phase: str
    query: str
    results: list[SearchResult]
    fused_results: list[FusedResult]
    latency_ms: int
    semantic_enabled: bool
    rerank_applied: bool
    entity_facets: list[SearchEntityFacet] = field(default_factory=list)


@dataclass(slots=True)
class PrefetchedSearchChunk:
    chunk_id: str
    document_title: str
    document_path: str
    document_type: str
    document_status: str
    project_slug: str
    heading_path: list[str]
    content: str
    version_number: int
    content_hash: str
    document_uid: str
    start_line: int | None
    end_line: int | None
    matched_terms: list[str] = field(default_factory=list)
    entities: list[SearchResultEntity] = field(default_factory=list)


@dataclass(slots=True)
class ResolvedVersionScope:
    snapshot_version_ids: tuple[UUID, ...] | None = None
    path_overrides: dict[str, str] = field(default_factory=dict)


def parse_query(
    query: str,
    project_scope: str | None = None,
    version_scope: str = "current",
) -> ParsedQuery:
    return ParsedQuery(
        raw=query,
        bm25_query=query,
        detected_terms=extract_technical_terms(query),
        version_scope=version_scope,
        project_scope=project_scope,
    )


def _parse_as_of_scope(version_scope: str) -> datetime | None:
    if not version_scope.startswith("as_of:"):
        return None

    raw_timestamp = version_scope.split(":", 1)[1]
    parsed = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("as_of scope must include a timezone-aware timestamp")
    return parsed


def _parse_branch_scope(version_scope: str) -> str | None:
    if not version_scope.startswith("branch:"):
        return None
    branch_name = version_scope.split(":", 1)[1].strip()
    return branch_name or None


def _parse_snapshot_scope(version_scope: str) -> str | None:
    if not version_scope.startswith("snapshot:"):
        return None
    snapshot_name = version_scope.split(":", 1)[1].strip()
    return snapshot_name or None


async def _resolve_version_scope(
    session: AsyncSession,
    *,
    version_scope: str,
    project_scope: str | None,
) -> ResolvedVersionScope:
    if version_scope == "current" or version_scope == "all":
        return ResolvedVersionScope()

    if version_scope.startswith("as_of:"):
        as_of_ts = _parse_as_of_scope(version_scope)
        if as_of_ts is None:
            return ResolvedVersionScope()
        statement = (
            select(VersionHeadEvent.version_id, VersionHeadEvent.canonical_path)
            .select_from(VersionHeadEvent)
            .join(Project, VersionHeadEvent.project_id == Project.id)
            .where(
                VersionHeadEvent.event_type == "save",
                VersionHeadEvent.valid_from <= as_of_ts,
                or_(
                    VersionHeadEvent.valid_to.is_(None),
                    VersionHeadEvent.valid_to > as_of_ts,
                ),
            )
        )
        if project_scope:
            statement = statement.where(Project.slug == project_scope)
        rows = await session.execute(statement)
        return ResolvedVersionScope(
            path_overrides={
                str(version_id): canonical_path
                for version_id, canonical_path in rows.fetchall()
            }
        )

    branch_name = _parse_branch_scope(version_scope)
    if branch_name is not None:
        statement = (
            select(VersionHeadEvent.version_id, VersionHeadEvent.canonical_path)
            .select_from(VersionHeadEvent)
            .join(Project, VersionHeadEvent.project_id == Project.id)
            .where(
                VersionHeadEvent.branch == branch_name,
                VersionHeadEvent.event_type == "save",
                VersionHeadEvent.valid_to.is_(None),
            )
        )
        if project_scope:
            statement = statement.where(Project.slug == project_scope)
        rows = await session.execute(statement)
        return ResolvedVersionScope(
            path_overrides={
                str(version_id): canonical_path
                for version_id, canonical_path in rows.fetchall()
            }
        )

    snapshot_name = _parse_snapshot_scope(version_scope)
    if snapshot_name is not None:
        snapshot_version_ids, path_overrides = await _resolve_snapshot_membership(
            session,
            snapshot_name=snapshot_name,
            project_scope=project_scope,
        )
        return ResolvedVersionScope(
            snapshot_version_ids=tuple(snapshot_version_ids),
            path_overrides=path_overrides,
        )

    return ResolvedVersionScope()


async def _resolve_snapshot_membership(
    session: AsyncSession,
    *,
    snapshot_name: str,
    project_scope: str | None,
) -> tuple[list[UUID], dict[str, str]]:
    project_statement = select(Project.slug, Project.filesystem_path)
    if project_scope:
        project_statement = project_statement.where(Project.slug == project_scope)
    project_rows = await session.execute(project_statement)

    scope_entries: dict[tuple[str, str, str], str] = {}
    for project_slug, filesystem_path in project_rows.fetchall():
        project_path = Path(filesystem_path)
        snapshots_path = project_path / ".piq" / "snapshots.yaml"
        if not snapshots_path.exists():
            continue
        snapshot_payload = yaml.safe_load(snapshots_path.read_text()) or {}
        snapshot = (snapshot_payload.get("snapshots") or {}).get(snapshot_name) or {}
        documents = snapshot.get("documents") or {}
        if not isinstance(documents, dict):
            continue
        for canonical_path, content_hash in documents.items():
            manifest_dir = resolve_manifest_dir(project_path, str(canonical_path), for_write=False)
            manifest = read_manifest(manifest_dir / "manifest.yaml")
            document_uid = manifest.get("document_uid")
            if not document_uid:
                continue
            key = (str(project_slug), str(document_uid), str(content_hash))
            scope_entries[key] = str(canonical_path)

    if not scope_entries:
        return [], {}

    filters = [
        and_(
            Project.slug == project_slug,
            Document.uid == document_uid,
            DocumentVersion.content_hash == content_hash,
        )
        for project_slug, document_uid, content_hash in scope_entries
    ]
    rows = await session.execute(
        select(
            DocumentVersion.id,
            Project.slug,
            Document.uid,
            DocumentVersion.content_hash,
        )
        .select_from(DocumentVersion)
        .join(Document, DocumentVersion.document_id == Document.id)
        .join(Project, Document.project_id == Project.id)
        .where(or_(*filters))
    )

    version_ids: list[UUID] = []
    path_overrides: dict[str, str] = {}
    for version_id, project_slug, document_uid, content_hash in rows.fetchall():
        key = (str(project_slug), str(document_uid), str(content_hash))
        override = scope_entries.get(key)
        if override is None:
            continue
        version_ids.append(version_id)
        path_overrides[str(version_id)] = override

    return version_ids, path_overrides


async def _resolve_retrieval_config(
    session: AsyncSession,
    search_options: SearchOptions | None,
) -> PipelineConfig:
    if search_options and search_options.retrieval_config_id is not None:
        retrieval_config = await session.get(PipelineConfig, search_options.retrieval_config_id)
        if retrieval_config is None:
            raise ValueError(
                f"retrieval config {search_options.retrieval_config_id} not found"
            )
        return retrieval_config
    return await get_retrieval_pipeline_config(session)


def _retrieval_settings(retrieval_config: PipelineConfig) -> tuple[int, dict[str, float]]:
    config = retrieval_config.config or {}
    rrf_k = int(config.get("rrf_k", RETRIEVAL_RRF_K))
    raw_weights = config.get("weights", {})
    weights = {
        "bm25": float(raw_weights.get("bm25", RETRIEVAL_WEIGHTS["bm25"])),
        "vector": float(raw_weights.get("vector", RETRIEVAL_WEIGHTS["vector"])),
        "terms": float(raw_weights.get("terms", RETRIEVAL_WEIGHTS["terms"])),
    }
    return rrf_k, weights


def fuse_results(
    *,
    bm25_results: list[RankedCandidate] | None = None,
    vector_results: list[RankedCandidate] | None = None,
    term_results: list[RankedCandidate] | None = None,
    k: int = RETRIEVAL_RRF_K,
    w_bm25: float = RETRIEVAL_WEIGHTS["bm25"],
    w_vector: float = RETRIEVAL_WEIGHTS["vector"],
    w_terms: float = RETRIEVAL_WEIGHTS["terms"],
) -> list[FusedResult]:
    scores: dict[str, FusedResult] = {}

    def apply(candidates: list[RankedCandidate], attr: str, weight: float) -> None:
        for candidate in candidates:
            fused = scores.setdefault(
                candidate.chunk_id,
                FusedResult(
                    chunk_id=candidate.chunk_id,
                    fused_score=0.0,
                ),
            )
            fused.fused_score += weight * (1.0 / (k + candidate.rank))
            setattr(fused, attr, candidate.rank)

    apply(bm25_results or [], "rank_bm25", w_bm25)
    apply(vector_results or [], "rank_vector", w_vector)
    apply(term_results or [], "rank_terms", w_terms)

    return sorted(scores.values(), key=lambda item: item.fused_score, reverse=True)


async def search_execution(
    session: AsyncSession,
    query: str,
    gateway=None,
    project_scope: str | None = None,
    version_scope: str = "current",
    limit: int = 20,
    search_options: SearchOptions | None = None,
) -> SearchExecution:
    context = await _prepare_search_context(
        session,
        query=query,
        gateway=gateway,
        project_scope=project_scope,
        version_scope=version_scope,
        search_options=search_options,
    )
    return await _execute_search(
        session,
        context=context,
        gateway=gateway,
        version_scope=version_scope,
        project_scope=project_scope,
        limit=limit,
        include_vector=True,
        phase="hybrid",
        log_search=True,
        search_options=search_options,
    )


async def search(
    session: AsyncSession,
    query: str,
    gateway=None,
    project_scope: str | None = None,
    version_scope: str = "current",
    limit: int = 20,
    search_options: SearchOptions | None = None,
) -> list[SearchResult]:
    execution = await search_execution(
        session=session,
        query=query,
        gateway=gateway,
        project_scope=project_scope,
        version_scope=version_scope,
        limit=limit,
        search_options=search_options,
    )
    return execution.results


async def stream_search(
    session: AsyncSession,
    query: str,
    gateway=None,
    project_scope: str | None = None,
    version_scope: str = "current",
    limit: int = 20,
    search_options: SearchOptions | None = None,
) -> AsyncIterator[SearchExecution]:
    context = await _prepare_search_context(
        session,
        query=query,
        gateway=gateway,
        project_scope=project_scope,
        version_scope=version_scope,
        search_options=search_options,
    )

    yield await _execute_search(
        session,
        context=context,
        gateway=gateway,
        version_scope=version_scope,
        project_scope=project_scope,
        limit=limit,
        include_vector=False,
        phase="lexical",
        log_search=False,
        search_options=search_options,
    )

    yield await _execute_search(
        session,
        context=context,
        gateway=gateway,
        version_scope=version_scope,
        project_scope=project_scope,
        limit=limit,
        include_vector=True,
        phase="reranked",
        log_search=True,
        search_options=search_options,
    )


async def _prepare_search_context(
    session: AsyncSession,
    *,
    query: str,
    gateway,
    project_scope: str | None,
    version_scope: str,
    search_options: SearchOptions | None,
) -> SearchExecutionContext:
    parsed = parse_query(query, project_scope, version_scope)
    resolved_scope = await _resolve_version_scope(
        session,
        version_scope=version_scope,
        project_scope=project_scope,
    )
    retrieval_config = await _resolve_retrieval_config(session, search_options)
    active_embedding_run_id = search_options.embedding_model_run_id if search_options else None
    if active_embedding_run_id is None and gateway and gateway.embedding:
        active_embedding_run = await get_active_embedding_model_run(session, gateway, create=False)
        if active_embedding_run is not None:
            active_embedding_run_id = active_embedding_run.id

    reranker_enabled = bool(gateway and getattr(gateway, "reranker", None))
    if search_options and search_options.reranker_enabled is not None:
        reranker_enabled = search_options.reranker_enabled and bool(
            gateway and getattr(gateway, "reranker", None)
        )
    reranker_model_run_id = search_options.reranker_model_run_id if search_options else None
    if reranker_enabled and reranker_model_run_id is None and gateway and gateway.reranker:
        reranker_model_run = await get_active_reranker_model_run(session, gateway, create=True)
        if reranker_model_run is not None:
            reranker_model_run_id = reranker_model_run.id

    rrf_k, weights = _retrieval_settings(retrieval_config)

    return SearchExecutionContext(
        query=query,
        parsed=parsed,
        resolved_scope=resolved_scope,
        retrieval_config_id=retrieval_config.id,
        active_embedding_run_id=active_embedding_run_id,
        semantic_enabled=(
            active_embedding_run_id is not None
            and bool(gateway and gateway.embedding)
        ),
        reranker_enabled=reranker_enabled,
        reranker_model_run_id=reranker_model_run_id,
        rrf_k=rrf_k,
        weight_bm25=weights["bm25"],
        weight_vector=weights["vector"],
        weight_terms=weights["terms"],
    )


async def _execute_search(
    session: AsyncSession,
    *,
    context: SearchExecutionContext,
    gateway,
    version_scope: str,
    project_scope: str | None,
    limit: int,
    include_vector: bool,
    phase: str,
    log_search: bool,
    search_options: SearchOptions | None,
) -> SearchExecution:
    started = time.monotonic()
    parsed = context.parsed

    bm25_results = await _bm25_search(
        session,
        parsed,
        version_scope,
        limit=100,
        resolved_scope=context.resolved_scope,
    )
    term_results = await _term_search(
        session,
        parsed,
        version_scope,
        limit=100,
        resolved_scope=context.resolved_scope,
    )

    vector_results: list[RankedCandidate] = []
    semantic_applied = False
    if (
        include_vector
        and gateway
        and gateway.embedding
        and context.active_embedding_run_id is not None
    ):
        try:
            vectors = await gateway.embed(
                [context.query],
                input_type="query",
                instruction=settings.embedding_query_instruction,
            )
            if vectors:
                semantic_applied = True
                vector_results = await _vector_search(
                    session,
                    query_embedding=vectors[0],
                    embedding_model_run_id=context.active_embedding_run_id,
                    version_scope=version_scope,
                    project_scope=project_scope,
                    limit=100,
                    resolved_scope=context.resolved_scope,
                )
        except Exception as exc:
            logger.warning("vector search unavailable: %s", exc)

    fused = fuse_results(
        bm25_results=bm25_results,
        vector_results=vector_results,
        term_results=term_results,
        k=context.rrf_k,
        w_bm25=context.weight_bm25,
        w_vector=context.weight_vector,
        w_terms=context.weight_terms,
    )

    rerank_applied = False
    if phase == "reranked" and context.reranker_enabled and gateway:
        fused, rerank_applied = await _rerank_search_results(
            session=session,
            fused=fused,
            query=context.query,
            gateway=gateway,
            top_n=(
                search_options.rerank_candidate_limit
                if search_options is not None
                else 50
            ),
        )

    results = await _build_limited_search_results(
        session=session,
        fused_results=fused,
        parsed=parsed,
        resolved_scope=context.resolved_scope,
        limit=limit,
        max_results_per_document=(
            search_options.max_results_per_document if search_options is not None else 3
        ),
        allowed_document_types=(
            search_options.allowed_document_types if search_options is not None else None
        ),
    )
    entity_facets = _build_entity_facets(results)

    elapsed_ms = int((time.monotonic() - started) * 1000)

    if log_search:
        await _log_search_run(
            session=session,
            query=context.query,
            parsed=parsed,
            retrieval_config_id=context.retrieval_config_id,
            embedding_model_run_id=context.active_embedding_run_id if include_vector else None,
            reranker_model_run_id=context.reranker_model_run_id if rerank_applied else None,
            version_scope=version_scope,
            project_scope=project_scope,
            elapsed_ms=elapsed_ms,
            fused_results=fused[:limit],
            results=results,
        )

    return SearchExecution(
        phase=phase,
        query=context.query,
        results=results,
        fused_results=fused[:limit],
        latency_ms=elapsed_ms,
        semantic_enabled=context.semantic_enabled if phase == "lexical" else semantic_applied,
        rerank_applied=rerank_applied,
        entity_facets=entity_facets,
    )


async def _rerank_search_results(
    *,
    session: AsyncSession,
    fused: list[FusedResult],
    query: str,
    gateway,
    top_n: int,
) -> tuple[list[FusedResult], bool]:
    if not fused or not gateway or not getattr(gateway, "reranker", None):
        return fused, False

    rerank_inputs = await _load_chunk_rerank_payloads(session, fused[:top_n])
    if not rerank_inputs:
        return fused, False

    documents = [payload for _, payload in rerank_inputs]
    reranked_fused = {str(item.chunk_id): item for item in fused[:top_n]}

    try:
        reranked_indices = await gateway.rerank(query, documents, top_n=top_n)
    except Exception as exc:
        logger.warning("reranking unavailable: %s", exc)
        return fused, False

    reordered: list[FusedResult] = []
    seen: set[str] = set()
    for index, score in reranked_indices:
        if index < 0 or index >= len(rerank_inputs):
            continue
        chunk_id = rerank_inputs[index][0]
        item = reranked_fused.get(chunk_id)
        if item is None:
            continue
        item.rerank_score = float(score)
        reordered.append(item)
        seen.add(chunk_id)

    for item in fused:
        if item.chunk_id not in seen:
            reordered.append(item)

    return reordered, True


async def _load_chunk_rerank_payloads(
    session: AsyncSession,
    fused_results: list[FusedResult],
) -> list[tuple[str, str]]:
    if not fused_results:
        return []

    chunk_ids = [UUID(item.chunk_id) for item in fused_results]
    result = await session.execute(
        select(DocumentChunk.id, DocumentChunk.heading_path, DocumentChunk.content).where(
            DocumentChunk.id.in_(chunk_ids)
        )
    )
    rows = {str(row[0]): row for row in result.fetchall()}

    payloads: list[tuple[str, str]] = []
    for item in fused_results:
        row = rows.get(item.chunk_id)
        if row is None:
            continue
        heading_path = " > ".join(row[1] or [])
        prefix = f"{heading_path}\n" if heading_path else ""
        payloads.append((item.chunk_id, prefix + row[2]))
    return payloads


async def _build_limited_search_results(
    *,
    session: AsyncSession,
    fused_results: list[FusedResult],
    parsed: ParsedQuery,
    resolved_scope: ResolvedVersionScope,
    limit: int,
    max_results_per_document: int | None,
    allowed_document_types: tuple[str, ...] | None,
) -> list[SearchResult]:
    results: list[SearchResult] = []
    per_document_counts: dict[str, int] = {}
    allowed_types = set(allowed_document_types or ())
    payloads = await _prefetch_search_chunks(
        session,
        fused_results,
        parsed,
        path_overrides=resolved_scope.path_overrides,
    )

    for item in fused_results:
        payload = payloads.get(item.chunk_id)
        if payload is None:
            continue
        if allowed_types and payload.document_type not in allowed_types:
            continue
        if max_results_per_document is not None:
            doc_count = per_document_counts.get(payload.document_uid, 0)
            if doc_count >= max_results_per_document:
                continue
            per_document_counts[payload.document_uid] = doc_count + 1

        snippet = payload.content.strip()
        if len(snippet) > 200:
            snippet = snippet[:200].rstrip() + "..."

        match_signals: list[str] = []
        if item.rank_bm25 is not None:
            match_signals.append("keyword")
        if item.rank_vector is not None:
            match_signals.append("semantic")
        if item.rank_terms is not None:
            match_signals.append("exact-term")

        matched_terms = payload.matched_terms
        if not matched_terms:
            matched_terms = [term.raw_text for term in parsed.detected_terms]

        results.append(
            SearchResult(
                document_title=payload.document_title,
                document_path=payload.document_path,
                document_type=payload.document_type,
                document_status=payload.document_status,
                project_slug=payload.project_slug,
                heading_path=" > ".join(payload.heading_path),
                snippet=snippet,
                version_number=payload.version_number,
                content_hash=payload.content_hash,
                fused_score=item.fused_score,
                matched_terms=matched_terms,
                document_uid=payload.document_uid,
                chunk_id=payload.chunk_id,
                line_start=payload.start_line or 0,
                line_end=payload.end_line or 0,
                match_signals=match_signals,
                entities=list(payload.entities),
            )
        )
        if len(results) >= limit:
            break

    return results


async def _prefetch_search_chunks(
    session: AsyncSession,
    fused_results: list[FusedResult],
    parsed: ParsedQuery,
    *,
    path_overrides: dict[str, str] | None = None,
) -> dict[str, PrefetchedSearchChunk]:
    if not fused_results:
        return {}

    chunk_ids = [UUID(item.chunk_id) for item in fused_results]
    chunk_rows = await session.execute(
        select(
            DocumentChunk.id,
            DocumentChunk.heading_path,
            DocumentChunk.content,
            DocumentChunk.start_line,
            DocumentChunk.end_line,
            DocumentVersion.id,
            DocumentVersion.version_number,
            DocumentVersion.content_hash,
            Document.uid,
            Document.title,
            Document.canonical_path,
            Document.doc_type,
            Document.status,
            Project.slug,
        )
        .select_from(DocumentChunk)
        .join(DocumentVersion, DocumentChunk.version_id == DocumentVersion.id)
        .join(Document, DocumentVersion.document_id == Document.id)
        .join(Project, Document.project_id == Project.id)
        .where(DocumentChunk.id.in_(chunk_ids))
    )

    payloads: dict[str, PrefetchedSearchChunk] = {}
    for row in chunk_rows.fetchall():
        chunk_id = str(row[0])
        payloads[chunk_id] = PrefetchedSearchChunk(
            chunk_id=chunk_id,
            heading_path=row[1] or [],
            content=row[2],
            start_line=row[3],
            end_line=row[4],
            version_number=row[6],
            content_hash=row[7],
            document_uid=row[8],
            document_title=row[9],
            document_path=(path_overrides or {}).get(str(row[5]), row[10]),
            document_type=row[11],
            document_status=row[12],
            project_slug=row[13],
        )

    if not payloads:
        return payloads

    db_chunk_ids = [UUID(chunk_id) for chunk_id in payloads]
    if parsed.detected_terms:
        normalized_terms = [term.normalized_text for term in parsed.detected_terms]
        term_rows = await session.execute(
            select(TechnicalTerm.chunk_id, TechnicalTerm.raw_text)
            .where(
                TechnicalTerm.chunk_id.in_(db_chunk_ids),
                TechnicalTerm.normalized_text.in_(normalized_terms),
            )
            .order_by(TechnicalTerm.chunk_id.asc(), TechnicalTerm.raw_text.asc())
        )
        for chunk_id, raw_text in term_rows.fetchall():
            if raw_text is None:
                continue
            key = str(chunk_id)
            payload = payloads.get(key)
            if payload is None or raw_text in payload.matched_terms:
                continue
            payload.matched_terms.append(raw_text)

    entity_rows = await session.execute(
        select(EntityMention.chunk_id, Entity.canonical_name, Entity.entity_type)
        .select_from(EntityMention)
        .join(Entity, EntityMention.entity_id == Entity.id)
        .where(EntityMention.chunk_id.in_(db_chunk_ids))
        .order_by(
            EntityMention.chunk_id.asc(),
            Entity.entity_type.asc(),
            Entity.canonical_name.asc(),
        )
    )
    seen_entities: dict[str, set[tuple[str, str]]] = {}
    for chunk_id, canonical_name, entity_type in entity_rows.fetchall():
        key = str(chunk_id)
        payload = payloads.get(key)
        if payload is None:
            continue
        pair = (canonical_name, entity_type)
        seen = seen_entities.setdefault(key, set())
        if pair in seen:
            continue
        seen.add(pair)
        payload.entities.append(
            SearchResultEntity(
                canonical_name=canonical_name,
                entity_type=entity_type,
            )
        )

    return payloads


def _build_scope_sql(
    version_scope: str,
    project_scope: str | None,
    resolved_scope: ResolvedVersionScope,
) -> tuple[str, dict]:
    clauses: list[str] = []
    params: dict[str, object] = {}

    if version_scope == "current":
        clauses.append("dv.id = d.current_version_id")
        clauses.append("d.status != 'deleted'")
    elif version_scope.startswith("branch:"):
        branch_name = _parse_branch_scope(version_scope)
        if branch_name is None:
            clauses.append("FALSE")
        else:
            params["branch_name"] = branch_name
            clauses.append(
                """
                dv.id IN (
                    SELECT vhe.version_id
                    FROM version_head_events vhe
                    WHERE vhe.document_id = d.id
                      AND vhe.branch = :branch_name
                      AND vhe.event_type = 'save'
                      AND vhe.valid_to IS NULL
                )
                """
            )
    elif version_scope.startswith("as_of:"):
        as_of_ts = _parse_as_of_scope(version_scope)
        params["as_of_ts"] = as_of_ts
        clauses.append(
            """
            dv.id IN (
                SELECT vhe.version_id
                FROM version_head_events vhe
                WHERE vhe.document_id = d.id
                  AND vhe.event_type = 'save'
                  AND vhe.valid_from <= :as_of_ts::timestamptz
                  AND (vhe.valid_to IS NULL OR vhe.valid_to > :as_of_ts::timestamptz)
            )
            """
        )
    elif version_scope.startswith("snapshot:"):
        snapshot_version_ids = resolved_scope.snapshot_version_ids or ()
        if not snapshot_version_ids:
            clauses.append("FALSE")
        else:
            params["snapshot_version_ids"] = list(snapshot_version_ids)
            clauses.append("dv.id = ANY(CAST(:snapshot_version_ids AS uuid[]))")

    if project_scope:
        clauses.append("p.slug = :project_scope")
        params["project_scope"] = project_scope

    return (" AND ".join(clauses) if clauses else "TRUE"), params


def _build_term_scope_filters(
    version_scope: str,
    project_scope: str | None,
    resolved_scope: ResolvedVersionScope,
) -> list[ColumnElement[bool]]:
    filters: list[ColumnElement[bool]] = []

    if version_scope == "current":
        filters.append(DocumentVersion.id == Document.current_version_id)
        filters.append(Document.status != "deleted")
    elif version_scope.startswith("branch:"):
        branch_name = _parse_branch_scope(version_scope)
        if branch_name is None:
            filters.append(false())
        else:
            filters.append(
                DocumentVersion.id.in_(
                    select(VersionHeadEvent.version_id).where(
                        VersionHeadEvent.document_id == Document.id,
                        VersionHeadEvent.branch == branch_name,
                        VersionHeadEvent.event_type == "save",
                        VersionHeadEvent.valid_to.is_(None),
                    )
                )
            )
    elif version_scope.startswith("as_of:"):
        as_of_ts = _parse_as_of_scope(version_scope)
        filters.append(
            DocumentVersion.id.in_(
                select(VersionHeadEvent.version_id).where(
                    VersionHeadEvent.document_id == Document.id,
                    VersionHeadEvent.event_type == "save",
                    VersionHeadEvent.valid_from <= as_of_ts,
                    or_(
                        VersionHeadEvent.valid_to.is_(None),
                        VersionHeadEvent.valid_to > as_of_ts,
                    ),
                )
            )
        )
    elif version_scope.startswith("snapshot:"):
        snapshot_version_ids = resolved_scope.snapshot_version_ids or ()
        if not snapshot_version_ids:
            filters.append(false())
        else:
            filters.append(DocumentVersion.id.in_(list(snapshot_version_ids)))

    if project_scope:
        filters.append(Project.slug == project_scope)

    return filters


def _build_entity_facets(
    results: list[SearchResult],
    *,
    limit: int = 20,
) -> list[SearchEntityFacet]:
    counts: dict[tuple[str, str], int] = {}
    for result in results:
        for entity in result.entities:
            key = (entity.canonical_name, entity.entity_type)
            counts[key] = counts.get(key, 0) + 1

    ranked = sorted(
        counts.items(),
        key=lambda item: (-item[1], item[0][1], item[0][0]),
    )
    return [
        SearchEntityFacet(
            canonical_name=canonical_name,
            entity_type=entity_type,
            count=count,
        )
        for (canonical_name, entity_type), count in ranked[:limit]
    ]


async def _bm25_search(
    session: AsyncSession,
    parsed: ParsedQuery,
    version_scope: str,
    limit: int,
    *,
    resolved_scope: ResolvedVersionScope,
) -> list[RankedCandidate]:
    scope_sql, params = _build_scope_sql(
        version_scope,
        parsed.project_scope,
        resolved_scope,
    )
    sql = text(
        f"""
        SELECT dc.id::text, pdb.score(dc.id) AS score
        FROM document_chunks dc
        JOIN document_versions dv ON dc.version_id = dv.id
        JOIN documents d ON dv.document_id = d.id
        JOIN projects p ON d.project_id = p.id
        WHERE dc.content ||| :query
          AND {scope_sql}
        ORDER BY pdb.score(dc.id) DESC
        LIMIT :limit
        """
    )
    try:
        result = await session.execute(sql, {"query": parsed.bm25_query, "limit": limit, **params})
        return [
            RankedCandidate(chunk_id=row[0], rank=index + 1, score=float(row[1] or 0.0))
            for index, row in enumerate(result.fetchall())
        ]
    except Exception as exc:
        logger.warning("bm25 search failed: %s", exc)
        return []


async def _vector_search(
    session: AsyncSession,
    *,
    query_embedding: list[float],
    embedding_model_run_id: UUID | None,
    version_scope: str,
    project_scope: str | None,
    limit: int,
    resolved_scope: ResolvedVersionScope,
) -> list[RankedCandidate]:
    if not query_embedding or embedding_model_run_id is None:
        return []
    if len(query_embedding) != settings.embedding_dimensions:
        logger.warning(
            "vector search skipped due to embedding dimension mismatch: got=%s expected=%s",
            len(query_embedding),
            settings.embedding_dimensions,
        )
        return []

    dims = len(query_embedding)
    distance = ChunkEmbedding.embedding.cosine_distance(query_embedding)
    query = (
        select(
            DocumentChunk.id,
            (1 - distance).label("similarity"),
        )
        .select_from(ChunkEmbedding)
        .join(DocumentChunk, ChunkEmbedding.chunk_id == DocumentChunk.id)
        .join(DocumentVersion, DocumentChunk.version_id == DocumentVersion.id)
        .join(Document, DocumentVersion.document_id == Document.id)
        .join(Project, Document.project_id == Project.id)
        .where(
            ChunkEmbedding.dimensions == dims,
            ChunkEmbedding.model_run_id == embedding_model_run_id,
        )
        .order_by(distance)
        .limit(limit)
    )

    for filter_clause in _build_term_scope_filters(
        version_scope,
        project_scope,
        resolved_scope,
    ):
        query = query.where(filter_clause)

    try:
        result = await session.execute(query)
        return [
            RankedCandidate(chunk_id=str(row[0]), rank=index + 1, score=float(row[1] or 0.0))
            for index, row in enumerate(result.fetchall())
        ]
    except Exception as exc:
        logger.warning("vector search failed: %s", exc)
        return []


async def _term_search(
    session: AsyncSession,
    parsed: ParsedQuery,
    version_scope: str,
    limit: int,
    *,
    resolved_scope: ResolvedVersionScope,
) -> list[RankedCandidate]:
    if not parsed.detected_terms:
        return []

    normalized_terms = [term.normalized_text for term in parsed.detected_terms]
    query = (
        select(TechnicalTerm.chunk_id, func.count().label("match_count"))
        .join(DocumentChunk, TechnicalTerm.chunk_id == DocumentChunk.id)
        .join(DocumentVersion, DocumentChunk.version_id == DocumentVersion.id)
        .join(Document, DocumentVersion.document_id == Document.id)
        .join(Project, Document.project_id == Project.id)
        .where(TechnicalTerm.normalized_text.in_(normalized_terms))
        .group_by(TechnicalTerm.chunk_id)
        .order_by(func.count().desc())
        .limit(limit)
    )

    for filter_clause in _build_term_scope_filters(
        version_scope,
        parsed.project_scope,
        resolved_scope,
    ):
        query = query.where(filter_clause)

    try:
        result = await session.execute(query)
        rows = result.fetchall()
        return [
            RankedCandidate(chunk_id=str(row[0]), rank=index + 1, score=float(row[1]))
            for index, row in enumerate(rows)
            if row[0] is not None
        ]
    except Exception as exc:
        logger.warning("term search failed: %s", exc)
        return []


async def _log_search_run(
    *,
    session: AsyncSession,
    query: str,
    parsed: ParsedQuery,
    retrieval_config_id: UUID | None,
    embedding_model_run_id: UUID | None,
    reranker_model_run_id: UUID | None,
    version_scope: str,
    project_scope: str | None,
    elapsed_ms: int,
    fused_results: list[FusedResult],
    results: list[SearchResult],
) -> None:
    try:
        search_run = SearchRun(
            query_text=query,
            parsed_query={
                "bm25_query": parsed.bm25_query,
                "terms": [term.raw_text for term in parsed.detected_terms],
                "version_scope": parsed.version_scope,
            },
            version_scope=version_scope,
            project_scope=project_scope,
            retrieval_config_id=retrieval_config_id,
            embedding_model_run_id=embedding_model_run_id,
            reranker_model_run_id=reranker_model_run_id,
            result_count=len(results),
            latency_ms=elapsed_ms,
        )
        session.add(search_run)
        await session.flush()

        for index, item in enumerate(fused_results, start=1):
            session.add(
                SearchRunResult(
                    search_run_id=search_run.id,
                    chunk_id=UUID(item.chunk_id),
                    rank_bm25=item.rank_bm25,
                        rank_vector=item.rank_vector,
                        rank_entity=item.rank_terms,
                        fused_score=item.fused_score,
                        rerank_score=item.rerank_score,
                        final_rank=index,
                    )
                )
        await session.commit()
    except Exception as exc:
        logger.debug("search run logging skipped: %s", exc, exc_info=True)
        await session.rollback()
