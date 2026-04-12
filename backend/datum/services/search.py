"""Hybrid search with BM25, vectors, and technical terms."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import time
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from datum.models.core import Document, DocumentVersion, Project
from datum.models.search import ChunkEmbedding, DocumentChunk, SearchRun, SearchRunResult, TechnicalTerm
from datum.services.technical_terms import TermMatch, extract_technical_terms

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ParsedQuery:
    raw: str
    bm25_query: str
    detected_terms: list[TermMatch] = field(default_factory=list)
    version_scope: str = "current"
    project_scope: Optional[str] = None


@dataclass(slots=True)
class RankedCandidate:
    chunk_id: str
    rank: int
    score: float = 0.0


@dataclass(slots=True)
class FusedResult:
    chunk_id: str
    fused_score: float
    rank_bm25: Optional[int] = None
    rank_vector: Optional[int] = None
    rank_terms: Optional[int] = None


@dataclass(slots=True)
class SearchResult:
    document_title: str
    document_path: str
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


def parse_query(query: str, project_scope: Optional[str] = None) -> ParsedQuery:
    return ParsedQuery(
        raw=query,
        bm25_query=query,
        detected_terms=extract_technical_terms(query),
        project_scope=project_scope,
    )


def fuse_results(
    *,
    bm25_results: Optional[list[RankedCandidate]] = None,
    vector_results: Optional[list[RankedCandidate]] = None,
    term_results: Optional[list[RankedCandidate]] = None,
    k: int = 60,
    w_bm25: float = 1.0,
    w_vector: float = 1.0,
    w_terms: float = 0.5,
) -> list[FusedResult]:
    scores: dict[str, FusedResult] = {}

    def apply(candidates: list[RankedCandidate], attr: str, weight: float) -> None:
        for candidate in candidates:
            fused = scores.setdefault(candidate.chunk_id, FusedResult(chunk_id=candidate.chunk_id, fused_score=0.0))
            fused.fused_score += weight * (1.0 / (k + candidate.rank))
            setattr(fused, attr, candidate.rank)

    apply(bm25_results or [], "rank_bm25", w_bm25)
    apply(vector_results or [], "rank_vector", w_vector)
    apply(term_results or [], "rank_terms", w_terms)

    return sorted(scores.values(), key=lambda item: item.fused_score, reverse=True)


async def search(
    session: AsyncSession,
    query: str,
    gateway=None,
    project_scope: Optional[str] = None,
    version_scope: str = "current",
    limit: int = 20,
) -> list[SearchResult]:
    started = time.monotonic()
    parsed = parse_query(query, project_scope)

    bm25_results = await _bm25_search(session, parsed, version_scope, limit=100)
    vector_results: list[RankedCandidate] = []
    if gateway and gateway.embedding:
        try:
            vectors = await gateway.embed([query])
            if vectors:
                vector_results = await _vector_search(
                    session,
                    query_embedding=vectors[0],
                    version_scope=version_scope,
                    project_scope=project_scope,
                    limit=100,
                )
        except Exception as exc:
            logger.warning("vector search unavailable: %s", exc)

    term_results = await _term_search(session, parsed, version_scope, limit=100)
    fused = fuse_results(
        bm25_results=bm25_results,
        vector_results=vector_results,
        term_results=term_results,
    )

    results: list[SearchResult] = []
    for item in fused[:limit]:
        built = await _build_search_result(session, item, parsed)
        if built is not None:
            results.append(built)

    await _log_search_run(
        session=session,
        query=query,
        parsed=parsed,
        version_scope=version_scope,
        project_scope=project_scope,
        elapsed_ms=int((time.monotonic() - started) * 1000),
        fused_results=fused[:limit],
        results=results,
    )
    return results


def _build_scope_sql(version_scope: str, project_scope: Optional[str]) -> tuple[str, dict]:
    clauses: list[str] = []
    params: dict[str, object] = {}

    if version_scope == "current":
        clauses.append("dv.id = d.current_version_id")
    elif version_scope.startswith("as_of:"):
        as_of_ts = version_scope.split(":", 1)[1]
        params["as_of_ts"] = as_of_ts
        clauses.append(
            """
            dv.id IN (
                SELECT vhe.version_id
                FROM version_head_events vhe
                WHERE vhe.document_id = d.id
                  AND vhe.valid_from <= :as_of_ts::timestamptz
                  AND (vhe.valid_to IS NULL OR vhe.valid_to > :as_of_ts::timestamptz)
            )
            """
        )

    if project_scope:
        clauses.append("p.slug = :project_scope")
        params["project_scope"] = project_scope

    return (" AND ".join(clauses) if clauses else "TRUE"), params


async def _bm25_search(
    session: AsyncSession,
    parsed: ParsedQuery,
    version_scope: str,
    limit: int,
) -> list[RankedCandidate]:
    scope_sql, params = _build_scope_sql(version_scope, parsed.project_scope)
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
    version_scope: str,
    project_scope: Optional[str],
    limit: int,
) -> list[RankedCandidate]:
    if not query_embedding:
        return []

    scope_sql, params = _build_scope_sql(version_scope, project_scope)
    dims = len(query_embedding)
    embedding_literal = "[" + ",".join(str(value) for value in query_embedding) + "]"
    sql = text(
        f"""
        SELECT dc.id::text,
               1 - (ce.embedding <=> CAST(:embedding AS halfvec(1024))) AS similarity
        FROM chunk_embeddings ce
        JOIN document_chunks dc ON ce.chunk_id = dc.id
        JOIN document_versions dv ON dc.version_id = dv.id
        JOIN documents d ON dv.document_id = d.id
        JOIN projects p ON d.project_id = p.id
        WHERE ce.dimensions = :dimensions
          AND {scope_sql}
        ORDER BY ce.embedding <=> CAST(:embedding AS halfvec(1024))
        LIMIT :limit
        """
    )
    try:
        result = await session.execute(
            sql,
            {
                "embedding": embedding_literal,
                "dimensions": dims,
                "limit": limit,
                **params,
            },
        )
        return [
            RankedCandidate(chunk_id=row[0], rank=index + 1, score=float(row[1] or 0.0))
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

    if version_scope == "current":
        query = query.where(DocumentVersion.id == Document.current_version_id)
    if parsed.project_scope:
        query = query.where(Project.slug == parsed.project_scope)

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


async def _build_search_result(
    session: AsyncSession,
    fused: FusedResult,
    parsed: ParsedQuery,
) -> Optional[SearchResult]:
    try:
        chunk = await session.get(DocumentChunk, UUID(fused.chunk_id))
        if chunk is None:
            return None

        version = await session.get(DocumentVersion, chunk.version_id)
        document = await session.get(Document, version.document_id) if version else None
        project = await session.get(Project, document.project_id) if document else None
        if version is None or document is None or project is None:
            return None

        snippet = chunk.content.strip()
        if len(snippet) > 200:
            snippet = snippet[:200].rstrip() + "..."

        matched_terms = await _matched_terms_for_chunk(session, chunk.id, parsed)

        return SearchResult(
            document_title=document.title,
            document_path=document.canonical_path,
            project_slug=project.slug,
            heading_path=" > ".join(chunk.heading_path or []),
            snippet=snippet,
            version_number=version.version_number,
            content_hash=version.content_hash,
            fused_score=fused.fused_score,
            matched_terms=matched_terms,
            document_uid=document.uid,
            chunk_id=str(chunk.id),
            line_start=chunk.start_line or 0,
            line_end=chunk.end_line or 0,
        )
    except Exception as exc:
        logger.warning("failed to build search result: %s", exc)
        return None


async def _matched_terms_for_chunk(
    session: AsyncSession,
    chunk_id: UUID,
    parsed: ParsedQuery,
) -> list[str]:
    if not parsed.detected_terms:
        return []

    normalized_terms = [term.normalized_text for term in parsed.detected_terms]
    result = await session.execute(
        select(TechnicalTerm.raw_text)
        .where(
            TechnicalTerm.chunk_id == chunk_id,
            TechnicalTerm.normalized_text.in_(normalized_terms),
        )
        .order_by(TechnicalTerm.raw_text.asc())
    )
    matched = list(dict.fromkeys(row[0] for row in result.fetchall() if row[0]))
    if matched:
        return matched
    return [term.raw_text for term in parsed.detected_terms]


async def _log_search_run(
    *,
    session: AsyncSession,
    query: str,
    parsed: ParsedQuery,
    version_scope: str,
    project_scope: Optional[str],
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
            },
            version_scope=version_scope,
            project_scope=project_scope,
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
                    final_rank=index,
                )
            )
        await session.commit()
    except Exception as exc:
        logger.debug("search run logging skipped: %s", exc, exc_info=True)
        await session.rollback()
