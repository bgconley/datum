#!/usr/bin/env python3
"""Benchmark key Datum queries for Phase 8 performance tuning."""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time

from sqlalchemy import text

from datum.db import async_session_factory

QUERIES = {
    "hybrid_search": """
        SELECT dc.id, dc.content, dc.heading_path
        FROM document_chunks dc
        WHERE dc.content_tsv @@ plainto_tsquery('english', :query)
        LIMIT 20
    """,
    "vector_search": """
        SELECT ce.chunk_id,
               ce.embedding <=> (SELECT embedding FROM chunk_embeddings LIMIT 1) AS distance
        FROM chunk_embeddings ce
        ORDER BY distance
        LIMIT 20
    """,
    "entity_mentions": """
        SELECT e.canonical_name, COUNT(em.id)
        FROM entities e
        JOIN entity_mentions em ON em.entity_id = e.id
        GROUP BY e.canonical_name
        ORDER BY COUNT(em.id) DESC
        LIMIT 20
    """,
    "version_history": """
        SELECT dv.version_number, dv.content_hash, dv.created_at
        FROM document_versions dv
        JOIN documents d ON dv.document_id = d.id
        ORDER BY dv.created_at DESC
        LIMIT 50
    """,
}


async def benchmark_query(name: str, sql: str, iterations: int, query: str) -> None:
    timings: list[float] = []
    async with async_session_factory() as session:
        for _ in range(iterations):
            started = time.perf_counter()
            await session.execute(text(sql), {"query": query})
            timings.append((time.perf_counter() - started) * 1000)

    p95_index = min(len(timings) - 1, max(0, int(len(timings) * 0.95) - 1))
    ordered = sorted(timings)
    print(
        f"{name:16} "
        f"median={statistics.median(timings):6.1f}ms "
        f"p95={ordered[p95_index]:6.1f}ms "
        f"mean={statistics.mean(timings):6.1f}ms"
    )


async def main_async(iterations: int, query: str) -> None:
    print("Datum Query Benchmarks")
    print("=" * 48)
    for name, sql in QUERIES.items():
        try:
            await benchmark_query(name, sql, iterations, query)
        except Exception as exc:
            print(f"{name:16} ERROR {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark key Datum queries.")
    parser.add_argument("--iterations", type=int, default=10, help="runs per query")
    parser.add_argument("--query", default="datum", help="text query for BM25 benchmark")
    args = parser.parse_args()
    asyncio.run(main_async(args.iterations, args.query))


if __name__ == "__main__":
    main()
