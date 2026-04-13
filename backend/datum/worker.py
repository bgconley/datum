"""Datum ingestion worker."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from datum.config import settings
from datum.db import async_session_factory
from datum.models.core import Document, DocumentVersion, ModelRun, Project
from datum.models.search import (
    ChunkEmbedding,
    DocumentChunk,
    IngestionJob,
    TechnicalTerm,
    VersionText,
)
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
from datum.services.pipeline_configs import (
    get_active_embedding_model_run,
    get_chunking_pipeline_config,
    get_embedding_pipeline_config,
    get_technical_terms_pipeline_config,
    make_ingestion_job_idempotency_key,
)

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 2.0


async def process_job(session: AsyncSession, job: IngestionJob, gateway: ModelGateway) -> None:
    job.status = "running"
    job.started_at = datetime.now(UTC)
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

        if job.completed_at is None and job.status in {"completed", "skipped"}:
            job.completed_at = datetime.now(UTC)

        await session.commit()
    except Exception as exc:
        logger.exception("worker job failed: %s", job.id)
        await session.rollback()
        try:
            persisted_job = await session.get(IngestionJob, job.id)
            target = persisted_job or job
            target.status = "failed"
            target.error_message = str(exc)[:1000]
            target.completed_at = datetime.now(UTC)
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("worker failed to persist terminal failure state: %s", job.id)


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
        chunking_config = await get_chunking_pipeline_config(session)
        await _queue_job(
            session,
            project_id=job.project_id,
            version_id=version.id,
            job_type="chunk",
            content_hash=result.content_hash,
            priority=1,
            pipeline_config_id=chunking_config.id,
            pipeline_config_hash=chunking_config.config_hash,
        )


async def _handle_chunk_job(
    session: AsyncSession,
    job: IngestionJob,
    version: DocumentVersion,
    gateway: ModelGateway,
) -> None:
    chunking_config = await get_chunking_pipeline_config(session)
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

    existing_chunk_ids_result = await session.execute(
        select(DocumentChunk.id).where(DocumentChunk.version_id == version.id)
    )
    existing_chunk_ids = existing_chunk_ids_result.scalars().all()
    if existing_chunk_ids:
        await session.execute(
            delete(ChunkEmbedding).where(ChunkEmbedding.chunk_id.in_(existing_chunk_ids))
        )
        await session.execute(
            delete(TechnicalTerm).where(
                TechnicalTerm.chunk_id.in_(existing_chunk_ids),
                TechnicalTerm.version_id == version.id,
            )
        )
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
                chunking_run_id=chunking_config.id,
                source_text_hash=source_text_hash,
            )
        )
    await session.flush()

    technical_terms_config = await get_technical_terms_pipeline_config(session)
    await _queue_job(
        session,
        project_id=job.project_id,
        version_id=version.id,
        job_type="technical_terms",
        content_hash=source_text_hash,
        priority=1,
        pipeline_config_id=technical_terms_config.id,
        pipeline_config_hash=technical_terms_config.config_hash,
    )
    embedding_config = await get_embedding_pipeline_config(session, gateway)
    embedding_model_run = await get_active_embedding_model_run(session, gateway, create=True)
    await _queue_job(
        session,
        project_id=job.project_id,
        version_id=version.id,
        job_type="embed",
        content_hash=source_text_hash,
        priority=2,
        pipeline_config_id=embedding_config.id if embedding_config else None,
        pipeline_config_hash=(
            embedding_config.config_hash
            if embedding_config
            else "embedding-disabled"
        ),
        model_run_id=embedding_model_run.id if embedding_model_run else None,
    )


async def _handle_term_job(
    session: AsyncSession,
    job: IngestionJob,
    version: DocumentVersion,
) -> None:
    technical_terms_config = await get_technical_terms_pipeline_config(session)
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
                    pipeline_config_id=technical_terms_config.id,
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

    model_run = await _resolve_embedding_model_run(session, job, gateway)
    vectors = await run_embedding(chunk_models, gateway)

    chunk_ids = [row.id for row in chunk_rows]
    await session.execute(
        delete(ChunkEmbedding).where(
            ChunkEmbedding.chunk_id.in_(chunk_ids),
            ChunkEmbedding.model_run_id == model_run.id,
        )
    )

    for chunk_row, vector in zip(chunk_rows, vectors, strict=False):
        if len(vector) != settings.embedding_dimensions:
            raise ValueError(
                f"embedding dimensions {len(vector)} do not match configured "
                f"schema dimension {settings.embedding_dimensions}"
            )
        session.add(
            ChunkEmbedding(
                chunk_id=chunk_row.id,
                model_run_id=model_run.id,
                dimensions=len(vector),
                embedding=vector,
            )
        )

    model_run.items_processed = (model_run.items_processed or 0) + len(vectors)
    await session.flush()


async def _queue_job(
    session: AsyncSession,
    *,
    project_id: UUID,
    version_id: UUID,
    job_type: str,
    content_hash: str,
    priority: int,
    pipeline_config_hash: str,
    pipeline_config_id: UUID | None = None,
    model_run_id: UUID | None = None,
) -> None:
    idem_key = make_ingestion_job_idempotency_key(
        project_id=project_id,
        version_id=version_id,
        job_type=job_type,
        content_hash=content_hash,
        pipeline_config_hash=pipeline_config_hash,
        model_run_id=model_run_id,
    )

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
            pipeline_config_id=pipeline_config_id,
            content_hash=content_hash,
            idempotency_key=idem_key,
            model_run_id=model_run_id,
        )
    )
    await session.flush()


async def _resolve_embedding_model_run(
    session: AsyncSession,
    job: IngestionJob,
    gateway: ModelGateway,
) -> ModelRun:
    if job.model_run_id is not None:
        existing = await session.get(ModelRun, job.model_run_id)
        if existing is not None:
            return existing

    model_run = await get_active_embedding_model_run(session, gateway, create=True)
    if model_run is None:
        raise RuntimeError("embedding model config missing")

    job.model_run_id = model_run.id
    return model_run


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
