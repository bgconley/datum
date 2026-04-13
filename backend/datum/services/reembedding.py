"""Re-embedding service for existing chunk corpora."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from datum.config import settings
from datum.models.core import Document, DocumentVersion, ModelRun
from datum.models.search import ChunkEmbedding, DocumentChunk, IngestionJob
from datum.services.pipeline_configs import make_ingestion_job_idempotency_key, stable_config_hash

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ReembeddingPlan:
    model_name: str
    model_run_id: UUID | None
    total_chunks: int
    batch_size: int
    estimated_batches: int


async def plan_reembedding(
    session: AsyncSession,
    model_name: str,
    batch_size: int = 64,
) -> ReembeddingPlan:
    result = await session.execute(select(func.count()).select_from(DocumentChunk))
    total_chunks = int(result.scalar() or 0)
    estimated_batches = (total_chunks + batch_size - 1) // batch_size if total_chunks else 0
    return ReembeddingPlan(
        model_name=model_name,
        model_run_id=None,
        total_chunks=total_chunks,
        batch_size=batch_size,
        estimated_batches=estimated_batches,
    )


async def start_reembedding(
    session: AsyncSession,
    model_name: str,
    model_version: str | None = None,
    dimensions: int = settings.embedding_dimensions,
    config: dict | None = None,
    batch_size: int = 64,
) -> UUID:
    model_payload = config or {
        "dimensions": dimensions,
        "batch_size": batch_size,
        "model_name": model_name,
    }
    pipeline_config_hash = stable_config_hash(model_payload)

    model_run = ModelRun(
        model_name=model_name,
        model_version=model_version or pipeline_config_hash,
        task="embedding",
        config=model_payload,
        started_at=datetime.now(UTC),
    )
    session.add(model_run)
    await session.flush()

    version_ids_result = await session.execute(select(DocumentChunk.version_id).distinct())
    version_ids = list(version_ids_result.scalars().all())

    queued = 0
    for version_id in version_ids:
        version = await session.get(DocumentVersion, version_id)
        if version is None:
            continue
        document = await session.get(Document, version.document_id)
        if document is None:
            continue

        idem_key = make_ingestion_job_idempotency_key(
            project_id=document.project_id,
            version_id=version_id,
            job_type="embed",
            content_hash=version.content_hash,
            pipeline_config_hash=pipeline_config_hash,
            model_run_id=model_run.id,
        )
        existing = await session.execute(
            select(IngestionJob).where(IngestionJob.idempotency_key == idem_key)
        )
        if existing.scalar_one_or_none() is not None:
            continue

        session.add(
            IngestionJob(
                project_id=document.project_id,
                version_id=version_id,
                job_type="embed",
                status="queued",
                priority=2,
                model_run_id=model_run.id,
                content_hash=version.content_hash,
                idempotency_key=idem_key,
            )
        )
        queued += 1

    await session.commit()
    logger.info("queued %s re-embedding jobs for model run %s", queued, model_run.id)
    return model_run.id


async def get_embedding_stats(session: AsyncSession) -> list[dict[str, str | int | None]]:
    result = await session.execute(
        text(
            """
            SELECT mr.model_name,
                   mr.id::text,
                   COUNT(ce.id) AS embedding_count,
                   mr.started_at,
                   mr.completed_at
            FROM model_runs mr
            LEFT JOIN chunk_embeddings ce ON ce.model_run_id = mr.id
            WHERE mr.task = 'embedding'
            GROUP BY mr.model_name, mr.id, mr.started_at, mr.completed_at
            ORDER BY mr.started_at DESC NULLS LAST
            """
        )
    )
    return [
        {
            "model_name": row[0],
            "model_run_id": row[1],
            "embedding_count": int(row[2] or 0),
            "started_at": row[3].isoformat() if row[3] is not None else None,
            "completed_at": row[4].isoformat() if row[4] is not None else None,
        }
        for row in result.fetchall()
    ]


async def drop_embeddings(session: AsyncSession, model_run_id: UUID) -> int:
    count_result = await session.execute(
        select(func.count())
        .select_from(ChunkEmbedding)
        .where(ChunkEmbedding.model_run_id == model_run_id)
    )
    deleted = int(count_result.scalar() or 0)
    result = await session.execute(
        text("DELETE FROM chunk_embeddings WHERE model_run_id = :model_run_id"),
        {"model_run_id": model_run_id},
    )
    await session.commit()
    del result
    logger.info("dropped %s embeddings for model run %s", deleted, model_run_id)
    return deleted
