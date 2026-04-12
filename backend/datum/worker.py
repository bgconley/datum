"""Datum ingestion worker."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Optional
from uuid import UUID

from sqlalchemy import delete, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from datum.db import async_session_factory
from datum.models.core import Document, DocumentVersion, ModelRun, Project
from datum.models.search import ChunkEmbedding, DocumentChunk, IngestionJob, TechnicalTerm, VersionText
from datum.services.chunking import Chunk
from datum.services.filesystem import compute_content_hash
from datum.services.ingestion import (
    IngestionContext,
    run_chunking,
    run_embedding,
    run_extraction_async,
    run_technical_terms,
)
from datum.services.model_gateway import ModelGateway, build_model_gateway

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 2.0


async def process_job(session: AsyncSession, job: IngestionJob, gateway: ModelGateway) -> None:
    job.status = "running"
    job.started_at = datetime.now(timezone.utc)
    await session.commit()

    try:
        version = await session.get(DocumentVersion, job.version_id)
        if version is None:
            raise ValueError(f"version not found for job {job.id}")

        document = await session.get(Document, version.document_id)
        if document is None:
            raise ValueError(f"document not found for version {version.id}")

        project = await session.get(Project, document.project_id)
        if project is None:
            raise ValueError(f"project not found for document {document.id}")

        ctx = IngestionContext(
            project_path=Path(project.filesystem_path),
            canonical_path=document.canonical_path,
        )

        if job.job_type == "extract":
            await _handle_extract_job(session, job, version, ctx)
        elif job.job_type == "chunk":
            await _handle_chunk_job(session, job, version, gateway)
        elif job.job_type == "technical_terms":
            await _handle_term_job(session, job, version)
        elif job.job_type == "embed":
            await _handle_embed_job(session, job, version, gateway)
        else:
            raise ValueError(f"unsupported job type: {job.job_type}")

        if job.status == "running":
            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            await session.commit()
    except Exception as exc:
        job.status = "failed"
        job.error_message = str(exc)[:1000]
        job.completed_at = datetime.now(timezone.utc)
        await session.commit()
        logger.exception("worker job failed: %s", job.id)


async def _handle_extract_job(
    session: AsyncSession,
    job: IngestionJob,
    version: DocumentVersion,
    ctx: IngestionContext,
) -> None:
    result = await run_extraction_async(ctx)
    if result is None:
        job.status = "skipped"
        job.error_message = "source file missing"
        return

    existing = await session.execute(
        select(VersionText).where(
            VersionText.version_id == version.id,
            VersionText.text_kind == result.text_kind,
            VersionText.content_hash == result.content_hash,
        )
    )
    if existing.scalar_one_or_none() is None:
        session.add(
            VersionText(
                version_id=version.id,
                text_kind=result.text_kind,
                content=result.content,
                content_hash=result.content_hash,
            )
        )
        await session.flush()

    if result.text_kind != "unsupported" and result.content.strip():
        await _queue_job(
            session,
            project_id=job.project_id,
            version_id=version.id,
            job_type="chunk",
            content_hash=result.content_hash,
            priority=1,
        )


async def _handle_chunk_job(
    session: AsyncSession,
    job: IngestionJob,
    version: DocumentVersion,
    gateway: ModelGateway,
) -> None:
    text_result = await session.execute(
        select(VersionText)
        .where(
            VersionText.version_id == version.id,
            VersionText.text_kind.in_(["raw", "extracted"]),
        )
        .order_by(VersionText.created_at.desc())
        .limit(1)
    )
    version_text = text_result.scalar_one_or_none()
    if version_text is None:
        raise ValueError("no extracted text found")

    chunks = run_chunking(version_text.content)
    source_text_hash = compute_content_hash(version_text.content.encode("utf-8"))

    await session.execute(delete(DocumentChunk).where(DocumentChunk.version_id == version.id))
    for chunk in chunks:
        session.add(
            DocumentChunk(
                version_id=version.id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                heading_path=chunk.heading_path,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                start_char=chunk.start_char,
                end_char=chunk.end_char,
                token_count=chunk.token_count,
                content_hash=compute_content_hash(chunk.content.encode("utf-8")),
                source_text_hash=source_text_hash,
            )
        )
    await session.flush()

    await _queue_job(
        session,
        project_id=job.project_id,
        version_id=version.id,
        job_type="technical_terms",
        content_hash=source_text_hash,
        priority=1,
    )
    await _queue_job(
        session,
        project_id=job.project_id,
        version_id=version.id,
        job_type="embed",
        content_hash=source_text_hash,
        priority=2,
        pipeline_config_hash=_embedding_config_hash(gateway),
    )


async def _handle_term_job(session: AsyncSession, job: IngestionJob, version: DocumentVersion) -> None:
    chunk_result = await session.execute(
        select(DocumentChunk)
        .where(DocumentChunk.version_id == version.id)
        .order_by(DocumentChunk.chunk_index.asc())
    )
    chunks = chunk_result.scalars().all()
    if not chunks:
        raise ValueError("no chunks found")

    await session.execute(delete(TechnicalTerm).where(TechnicalTerm.version_id == version.id))

    source_text_result = await session.execute(
        select(VersionText)
        .where(
            VersionText.version_id == version.id,
            VersionText.text_kind.in_(["raw", "extracted"]),
        )
        .order_by(VersionText.created_at.desc())
        .limit(1)
    )
    version_text = source_text_result.scalar_one_or_none()
    source_text_hash = version_text.content_hash if version_text else None

    for chunk in chunks:
        for term in run_technical_terms(chunk.content):
            session.add(
                TechnicalTerm(
                    normalized_text=term.normalized_text,
                    raw_text=term.raw_text,
                    term_type=term.term_type,
                    chunk_id=chunk.id,
                    version_id=version.id,
                    start_char=chunk.start_char + term.start_char,
                    end_char=chunk.start_char + term.end_char,
                    extraction_method="regex",
                    confidence=term.confidence,
                    source_text_hash=source_text_hash,
                )
            )
    await session.flush()


async def _handle_embed_job(
    session: AsyncSession,
    job: IngestionJob,
    version: DocumentVersion,
    gateway: ModelGateway,
) -> None:
    if not gateway.embedding:
        job.status = "skipped"
        job.error_message = "embedding gateway not configured"
        return

    healthy = await gateway.check_health("embedding")
    if not healthy:
        job.status = "skipped"
        job.error_message = "embedding gateway unavailable"
        return

    chunk_result = await session.execute(
        select(DocumentChunk)
        .where(DocumentChunk.version_id == version.id)
        .order_by(DocumentChunk.chunk_index.asc())
    )
    chunk_rows = chunk_result.scalars().all()
    if not chunk_rows:
        raise ValueError("no chunks found")

    chunk_models = [
        Chunk(
            content=row.content,
            heading_path=row.heading_path or [],
            start_char=row.start_char,
            end_char=row.end_char,
            start_line=row.start_line or 0,
            end_line=row.end_line or 0,
            token_count=row.token_count or 0,
            chunk_index=row.chunk_index,
        )
        for row in chunk_rows
    ]

    model_run = await _create_model_run(session, gateway)
    vectors = await run_embedding(chunk_models, gateway)

    chunk_ids = [row.id for row in chunk_rows]
    await session.execute(
        delete(ChunkEmbedding).where(
            ChunkEmbedding.chunk_id.in_(chunk_ids),
            ChunkEmbedding.model_run_id == model_run.id,
        )
    )

    for chunk_row, vector in zip(chunk_rows, vectors, strict=False):
        vector_literal = "[" + ",".join(str(value) for value in vector) + "]"
        await session.execute(
            text(
                """
                INSERT INTO chunk_embeddings (id, chunk_id, model_run_id, dimensions, embedding, created_at)
                VALUES (gen_random_uuid(), :chunk_id, :model_run_id, :dimensions, CAST(:embedding AS halfvec(1024)), NOW())
                """
            ),
            {
                "chunk_id": str(chunk_row.id),
                "model_run_id": str(model_run.id),
                "dimensions": len(vector),
                "embedding": vector_literal,
            },
        )

    model_run.items_processed = len(vectors)
    model_run.completed_at = datetime.now(timezone.utc)
    await session.flush()


async def _queue_job(
    session: AsyncSession,
    *,
    project_id: UUID,
    version_id: UUID,
    job_type: str,
    content_hash: str,
    priority: int,
    pipeline_config_hash: str = "default",
    model_run_id: Optional[UUID] = None,
) -> None:
    model_part = str(model_run_id) if model_run_id else "none"
    idem_key = f"{project_id}:{version_id}:{job_type}:{content_hash}:{pipeline_config_hash}:{model_part}"

    existing = await session.execute(
        select(IngestionJob).where(IngestionJob.idempotency_key == idem_key)
    )
    if existing.scalar_one_or_none() is not None:
        return

    session.add(
        IngestionJob(
            project_id=project_id,
            version_id=version_id,
            job_type=job_type,
            status="queued",
            priority=priority,
            content_hash=content_hash,
            idempotency_key=idem_key,
            model_run_id=model_run_id,
        )
    )
    await session.flush()


async def _create_model_run(session: AsyncSession, gateway: ModelGateway) -> ModelRun:
    config = gateway.embedding
    if config is None:
        raise RuntimeError("embedding model config missing")

    run = ModelRun(
        model_name=config.name,
        model_version=None,
        task="embedding",
        config={
            "endpoint": config.endpoint,
            "protocol": config.protocol,
            "dimensions": config.dimensions,
            "batch_size": config.batch_size,
        },
        started_at=datetime.now(timezone.utc),
    )
    session.add(run)
    await session.flush()
    return run


def _embedding_config_hash(gateway: ModelGateway) -> str:
    config = gateway.embedding
    if config is None:
        return "embedding-disabled"
    return f"{config.name}:{config.protocol}:{config.dimensions}:{config.batch_size}:{config.endpoint}"


async def worker_loop() -> None:
    gateway = build_model_gateway()
    logger.info("worker starting")

    try:
        while True:
            async with async_session_factory() as session:
                try:
                    result = await session.execute(
                        select(IngestionJob)
                        .where(IngestionJob.status == "queued")
                        .order_by(IngestionJob.priority.asc(), IngestionJob.created_at.asc())
                        .limit(1)
                        .with_for_update(skip_locked=True)
                    )
                    job = result.scalar_one_or_none()
                except SQLAlchemyError as exc:
                    await session.rollback()
                    logger.info("worker waiting for migrations or database readiness: %s", exc)
                    await asyncio.sleep(POLL_INTERVAL_SECONDS)
                    continue

                if job is None:
                    await asyncio.sleep(POLL_INTERVAL_SECONDS)
                    continue

                logger.info("processing job %s (%s)", job.id, job.job_type)
                await process_job(session, job, gateway)
    finally:
        await gateway.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(worker_loop())


if __name__ == "__main__":
    main()
