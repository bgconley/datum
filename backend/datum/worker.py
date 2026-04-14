"""Datum ingestion worker."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from datum.config import settings
from datum.db import async_session_factory
from datum.models.core import Document, DocumentVersion, ModelRun, Project
from datum.models.intelligence import (
    Decision,
    DocumentLink,
    Entity,
    EntityMention,
    EntityRelationship,
    OpenQuestion,
    Requirement,
)
from datum.models.search import (
    ChunkEmbedding,
    DocumentChunk,
    IngestionJob,
    TechnicalTerm,
    VersionText,
)
from datum.services.candidate_extraction import (
    extract_decisions_from_adr,
    extract_open_questions,
    extract_requirements,
)
from datum.services.chunking import Chunk
from datum.services.entity_extraction import ENTITY_LABELS, extract_entities_gliner
from datum.services.filesystem import compute_content_hash, generate_uid
from datum.services.ingestion import (
    IngestionContext,
    run_chunking,
    run_embedding,
    run_extraction_async,
    run_technical_terms,
)
from datum.services.intelligence import (
    candidate_severity,
    decision_signature,
    open_question_signature,
    requirement_signature,
)
from datum.services.link_detection import detect_all_links
from datum.services.llm_candidates import extract_candidates_llm
from datum.services.llm_relationships import extract_relationships_llm
from datum.services.model_gateway import ModelGateway, build_model_gateway
from datum.services.pipeline_configs import (
    get_active_embedding_model_run,
    get_active_llm_model_run,
    get_active_ner_model_run,
    get_candidate_extraction_pipeline_config,
    get_chunking_pipeline_config,
    get_embedding_pipeline_config,
    get_link_detection_pipeline_config,
    get_llm_candidate_pipeline_config,
    get_llm_relationship_pipeline_config,
    get_ner_pipeline_config,
    get_schema_parse_pipeline_config,
    get_technical_terms_pipeline_config,
    make_ingestion_job_idempotency_key,
)
from datum.services.schema_intelligence import extract_schema_intelligence

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 2.0


async def process_job(session: AsyncSession, job: IngestionJob, gateway: ModelGateway) -> None:
    job_id = job.id
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
            await _handle_extract_job(session, job, version, ctx, gateway)
        elif job.job_type == "link_detect":
            await _handle_link_detect_job(session, job, version)
        elif job.job_type == "schema_parse":
            await _handle_schema_parse_job(session, job, version)
        elif job.job_type == "chunk":
            await _handle_chunk_job(session, job, version, gateway)
        elif job.job_type == "technical_terms":
            await _handle_term_job(session, job, version)
        elif job.job_type == "embed":
            await _handle_embed_job(session, job, version, gateway)
        elif job.job_type == "ner_gliner":
            await _handle_ner_job(session, job, version, gateway)
        elif job.job_type == "extract_candidates":
            await _handle_candidate_job(session, job, version)
        elif job.job_type == "relate_llm":
            await _handle_relationship_job(session, job, version, gateway)
        elif job.job_type == "extract_candidates_llm":
            await _handle_llm_candidate_job(session, job, version, gateway)
        else:
            raise ValueError(f"unsupported job type: {job.job_type}")

        if job.status == "running":
            job.status = "completed"

        if job.completed_at is None and job.status in {"completed", "skipped"}:
            job.completed_at = datetime.now(UTC)

        await session.commit()
    except Exception as exc:
        logger.exception("worker job failed: %s", job_id)
        await session.rollback()
        try:
            persisted_job = await session.get(IngestionJob, job_id)
            if persisted_job is None:
                raise RuntimeError(f"job disappeared before failure state could persist: {job_id}")

            persisted_job.status = "failed"
            persisted_job.error_message = str(exc)[:1000]
            persisted_job.completed_at = datetime.now(UTC)
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("worker failed to persist terminal failure state: %s", job_id)


async def _handle_extract_job(
    session: AsyncSession,
    job: IngestionJob,
    version: DocumentVersion,
    ctx: IngestionContext,
    gateway: ModelGateway,
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
        candidate_config = await get_candidate_extraction_pipeline_config(session)
        await _queue_job(
            session,
            project_id=job.project_id,
            version_id=version.id,
            job_type="extract_candidates",
            content_hash=result.content_hash,
            priority=3,
            pipeline_config_id=candidate_config.id,
            pipeline_config_hash=candidate_config.config_hash,
        )
        ner_config = await get_ner_pipeline_config(session, gateway)
        if ner_config is not None:
            await _queue_job(
                session,
                project_id=job.project_id,
                version_id=version.id,
                job_type="ner_gliner",
                content_hash=result.content_hash,
                priority=3,
                pipeline_config_id=ner_config.id,
                pipeline_config_hash=ner_config.config_hash,
            )
        link_config = await get_link_detection_pipeline_config(session)
        await _queue_job(
            session,
            project_id=job.project_id,
            version_id=version.id,
            job_type="link_detect",
            content_hash=result.content_hash,
            priority=3,
            pipeline_config_id=link_config.id,
            pipeline_config_hash=link_config.config_hash,
        )
        if _supports_schema_parse(ctx.canonical_path):
            schema_config = await get_schema_parse_pipeline_config(session)
            await _queue_job(
                session,
                project_id=job.project_id,
                version_id=version.id,
                job_type="schema_parse",
                content_hash=result.content_hash,
                priority=3,
                pipeline_config_id=schema_config.id,
                pipeline_config_hash=schema_config.config_hash,
            )
        llm_candidate_config = await get_llm_candidate_pipeline_config(session, gateway)
        llm_model_run = await get_active_llm_model_run(session, gateway, create=True)
        if llm_candidate_config is not None and llm_model_run is not None:
            await _queue_job(
                session,
                project_id=job.project_id,
                version_id=version.id,
                job_type="extract_candidates_llm",
                content_hash=result.content_hash,
                priority=4,
                pipeline_config_id=llm_candidate_config.id,
                pipeline_config_hash=llm_candidate_config.config_hash,
                model_run_id=llm_model_run.id,
            )


async def _handle_link_detect_job(
    session: AsyncSession,
    job: IngestionJob,
    version: DocumentVersion,
) -> None:
    version_text = await _load_latest_version_text(session, version.id)
    if version_text is None or not version_text.content.strip():
        job.status = "skipped"
        job.error_message = "no extracted text found"
        return

    existing_docs_result = await session.execute(
        select(Document).where(Document.project_id == job.project_id)
    )
    documents = existing_docs_result.scalars().all()
    doc_by_path = {document.canonical_path: document for document in documents}
    links = detect_all_links(version_text.content, set(doc_by_path))

    await session.execute(
        delete(DocumentLink).where(
            DocumentLink.source_version_id == version.id,
            DocumentLink.auto_detected.is_(True),
        )
    )

    for link in links:
        target_document = doc_by_path.get(link.target_path)
        if target_document is None:
            continue
        session.add(
            DocumentLink(
                source_version_id=version.id,
                target_document_id=target_document.id,
                target_version_id=target_document.current_version_id,
                link_type=link.link_type,
                anchor_text=link.anchor_text,
                auto_detected=True,
                confidence=link.confidence,
            )
        )
    await session.flush()


async def _handle_schema_parse_job(
    session: AsyncSession,
    job: IngestionJob,
    version: DocumentVersion,
) -> None:
    version_text = await _load_latest_version_text(session, version.id)
    document = await session.get(Document, version.document_id)
    if version_text is None or document is None:
        job.status = "skipped"
        job.error_message = "no extracted text found"
        return

    suffix = Path(document.canonical_path).suffix
    entities, relationships = extract_schema_intelligence(version_text.content, suffix)
    if not entities and not relationships:
        job.status = "skipped"
        job.error_message = "no schema entities detected"
        return

    entity_map: dict[tuple[str, str], Entity] = {}
    for schema_entity in entities:
        entity_row = await _get_or_create_entity(
            session,
            entity_type=schema_entity.entity_type,
            canonical_name=schema_entity.name,
            metadata=schema_entity.properties or None,
        )
        entity_map[(schema_entity.entity_type, schema_entity.name)] = entity_row

    await session.execute(
        delete(EntityRelationship).where(
            EntityRelationship.evidence_version_id == version.id,
            EntityRelationship.extraction_method == "parser",
        )
    )

    for relationship in relationships:
        source_entity = _resolve_schema_relationship_entity(relationship.source, entity_map)
        target_entity = _resolve_schema_relationship_entity(relationship.target, entity_map)
        if source_entity is None or target_entity is None:
            continue
        session.add(
            EntityRelationship(
                source_entity_id=source_entity.id,
                target_entity_id=target_entity.id,
                relationship_type=relationship.relationship_type,
                evidence_version_id=version.id,
                evidence_text=relationship.evidence_text,
                extraction_method="parser",
                confidence=1.0,
            )
        )
    await session.flush()


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


async def _handle_ner_job(
    session: AsyncSession,
    job: IngestionJob,
    version: DocumentVersion,
    gateway: ModelGateway,
) -> None:
    if not gateway.ner:
        job.status = "skipped"
        job.error_message = "ner gateway not configured"
        return

    healthy = await gateway.check_health("ner")
    if not healthy:
        job.status = "skipped"
        job.error_message = "ner gateway unavailable"
        return

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
    if version_text is None or not version_text.content.strip():
        job.status = "skipped"
        job.error_message = "no extracted text found"
        return

    chunk_result = await session.execute(
        select(DocumentChunk)
        .where(DocumentChunk.version_id == version.id)
        .order_by(DocumentChunk.chunk_index.asc())
    )
    chunks = chunk_result.scalars().all()
    if not chunks:
        raise ValueError("no chunks found")

    await session.execute(delete(EntityMention).where(EntityMention.version_id == version.id))

    entities = await extract_entities_gliner(
        version_text.content,
        endpoint=gateway.ner.endpoint,
        labels=ENTITY_LABELS,
        threshold=settings.ner_threshold,
    )
    if not entities:
        await session.flush()
        return

    model_run = await _resolve_ner_model_run(session, gateway)
    entity_cache: dict[tuple[str, str], Entity] = {}
    extracted_at = datetime.now(UTC)

    for entity_candidate in entities:
        cache_key = (entity_candidate.entity_type, entity_candidate.canonical_name)
        entity_row = entity_cache.get(cache_key)
        if entity_row is None:
            existing_result = await session.execute(
                select(Entity).where(
                    Entity.entity_type == entity_candidate.entity_type,
                    Entity.canonical_name == entity_candidate.canonical_name,
                )
            )
            entity_row = existing_result.scalar_one_or_none()
            if entity_row is None:
                entity_row = Entity(
                    entity_type=entity_candidate.entity_type,
                    canonical_name=entity_candidate.canonical_name,
                    first_seen_at=extracted_at,
                    last_seen_at=extracted_at,
                )
                session.add(entity_row)
                await session.flush()
            else:
                entity_row.last_seen_at = extracted_at
            entity_cache[cache_key] = entity_row

        session.add(
            EntityMention(
                entity_id=entity_row.id,
                chunk_id=_match_chunk_for_span(
                    chunks,
                    entity_candidate.start_char,
                    entity_candidate.end_char,
                ),
                version_id=version.id,
                extraction_method=entity_candidate.extraction_method,
                model_run_id=model_run.id if model_run else None,
                confidence=entity_candidate.confidence,
                text_start_char=entity_candidate.start_char,
                text_end_char=entity_candidate.end_char,
                raw_text=entity_candidate.raw_text,
            )
        )

    if model_run is not None:
        model_run.items_processed = (model_run.items_processed or 0) + len(entities)

    llm_relationship_config = await get_llm_relationship_pipeline_config(session, gateway)
    llm_model_run = await get_active_llm_model_run(session, gateway, create=True)
    if llm_relationship_config is not None and llm_model_run is not None:
        await _queue_job(
            session,
            project_id=job.project_id,
            version_id=version.id,
            job_type="relate_llm",
            content_hash=job.content_hash or version_text.content_hash,
            priority=4,
            pipeline_config_id=llm_relationship_config.id,
            pipeline_config_hash=llm_relationship_config.config_hash,
            model_run_id=llm_model_run.id,
        )

    await session.flush()


async def _handle_relationship_job(
    session: AsyncSession,
    job: IngestionJob,
    version: DocumentVersion,
    gateway: ModelGateway,
) -> None:
    if gateway.llm is None:
        job.status = "skipped"
        job.error_message = "llm gateway not configured"
        return
    if not await gateway.check_health("llm"):
        job.status = "skipped"
        job.error_message = "llm gateway unavailable"
        return

    chunk_result = await session.execute(
        select(DocumentChunk)
        .where(DocumentChunk.version_id == version.id)
        .order_by(DocumentChunk.chunk_index.asc())
    )
    chunks = chunk_result.scalars().all()
    if not chunks:
        job.status = "skipped"
        job.error_message = "no chunks found"
        return

    mention_result = await session.execute(
        select(EntityMention, Entity)
        .join(Entity, EntityMention.entity_id == Entity.id)
        .where(EntityMention.version_id == version.id)
    )
    mentions = mention_result.all()
    if not mentions:
        job.status = "skipped"
        job.error_message = "no entities found"
        return

    entity_by_name: dict[str, Entity] = {}
    chunk_entity_names: dict[UUID, set[str]] = {}
    for mention, entity in mentions:
        entity_by_name.setdefault(entity.canonical_name, entity)
        if mention.chunk_id is not None:
            chunk_entity_names.setdefault(mention.chunk_id, set()).add(entity.canonical_name)

    await session.execute(
        delete(EntityRelationship).where(
            EntityRelationship.evidence_version_id == version.id,
            EntityRelationship.extraction_method == "llm",
        )
    )

    model_run = await _resolve_llm_model_run(session, job, gateway)
    relationship_count = 0
    for chunk in chunks:
        names = sorted(chunk_entity_names.get(chunk.id, set()))
        if len(names) < 2:
            continue
        candidates = await extract_relationships_llm(chunk.content, names, gateway)
        for candidate in candidates:
            source_entity = entity_by_name.get(candidate.source_entity)
            target_entity = entity_by_name.get(candidate.target_entity)
            if source_entity is None or target_entity is None:
                continue
            session.add(
                EntityRelationship(
                    source_entity_id=source_entity.id,
                    target_entity_id=target_entity.id,
                    relationship_type=candidate.relationship_type,
                    evidence_version_id=version.id,
                    evidence_chunk_id=chunk.id,
                    evidence_text=candidate.evidence_text or chunk.content[:240],
                    extraction_method="llm",
                    model_run_id=model_run.id if model_run is not None else None,
                    confidence=candidate.confidence,
                )
            )
            relationship_count += 1
    if model_run is not None:
        model_run.items_processed = (model_run.items_processed or 0) + relationship_count
    await session.flush()


async def _handle_llm_candidate_job(
    session: AsyncSession,
    job: IngestionJob,
    version: DocumentVersion,
    gateway: ModelGateway,
) -> None:
    if gateway.llm is None:
        job.status = "skipped"
        job.error_message = "llm gateway not configured"
        return
    if not await gateway.check_health("llm"):
        job.status = "skipped"
        job.error_message = "llm gateway unavailable"
        return

    version_text = await _load_latest_version_text(session, version.id)
    document = await session.get(Document, version.document_id)
    if version_text is None or document is None or not version_text.content.strip():
        job.status = "skipped"
        job.error_message = "no extracted text found"
        return

    model_run = await _resolve_llm_model_run(session, job, gateway)
    decision_rows_result = await session.execute(
        select(Decision).where(Decision.project_id == job.project_id)
    )
    decision_rows = decision_rows_result.scalars().all()
    requirement_rows_result = await session.execute(
        select(Requirement).where(Requirement.project_id == job.project_id)
    )
    requirement_rows = requirement_rows_result.scalars().all()
    question_rows_result = await session.execute(
        select(OpenQuestion).where(OpenQuestion.project_id == job.project_id)
    )
    question_rows = question_rows_result.scalars().all()

    decision_by_signature = {
        decision_signature(row.title, row.decision, row.consequences): row
        for row in decision_rows
    }
    requirement_by_signature = {
        requirement_signature(row.requirement_id, row.title, row.description, row.priority): row
        for row in requirement_rows
    }
    question_by_signature = {
        open_question_signature(row.question, row.context): row
        for row in question_rows
    }

    extracted_decision_signatures: set[str] = set()
    extracted_requirement_signatures: set[str] = set()
    extracted_question_signatures: set[str] = set()

    candidates = await extract_candidates_llm(version_text.content, document.doc_type, gateway)
    for candidate in candidates:
        if candidate.candidate_type == "decision":
            decision_text = candidate.description or candidate.title
            signature = decision_signature(candidate.title, decision_text, None)
            extracted_decision_signatures.add(signature)
            existing = decision_by_signature.get(signature)
            if existing is None:
                session.add(
                    Decision(
                        uid=generate_uid("dec"),
                        project_id=job.project_id,
                        title=candidate.title,
                        status="proposed",
                        context=candidate.evidence_text or None,
                        decision=decision_text,
                        curation_status="candidate",
                        source_version_id=version.id,
                        first_seen_version_id=version.id,
                        last_seen_version_id=version.id,
                        extraction_method="llm",
                        model_run_id=model_run.id if model_run is not None else None,
                        confidence=candidate.confidence,
                    )
                )
                continue

            existing.source_version_id = version.id
            existing.last_seen_version_id = version.id
            existing.extraction_method = "llm"
            existing.model_run_id = model_run.id if model_run is not None else None
            existing.confidence = candidate.confidence
            if existing.curation_status == "candidate":
                existing.title = candidate.title
                existing.context = candidate.evidence_text or existing.context
                existing.decision = decision_text
                existing.status = "proposed"
            continue

        if candidate.candidate_type == "requirement":
            description = candidate.description or candidate.evidence_text or None
            severity = candidate_severity("requirement", "llm")
            priority = "must" if severity == "high" else None
            signature = requirement_signature(None, candidate.title, description, priority)
            extracted_requirement_signatures.add(signature)
            existing_requirement = requirement_by_signature.get(signature)
            if existing_requirement is None:
                session.add(
                    Requirement(
                        uid=generate_uid("req"),
                        project_id=job.project_id,
                        title=candidate.title,
                        description=description,
                        priority=priority,
                        curation_status="candidate",
                        source_version_id=version.id,
                        first_seen_version_id=version.id,
                        last_seen_version_id=version.id,
                        extraction_method="llm",
                        model_run_id=model_run.id if model_run is not None else None,
                        confidence=candidate.confidence,
                    )
                )
                continue

            existing_requirement.source_version_id = version.id
            existing_requirement.last_seen_version_id = version.id
            existing_requirement.extraction_method = "llm"
            existing_requirement.model_run_id = model_run.id if model_run is not None else None
            existing_requirement.confidence = candidate.confidence
            if existing_requirement.curation_status == "candidate":
                existing_requirement.title = candidate.title
                existing_requirement.description = description
                existing_requirement.priority = priority
            continue

        question = candidate.title if candidate.title.endswith("?") else f"{candidate.title}?"
        context = candidate.description or candidate.evidence_text or None
        signature = open_question_signature(question, context)
        extracted_question_signatures.add(signature)
        existing_question = question_by_signature.get(signature)
        if existing_question is None:
            session.add(
                OpenQuestion(
                    project_id=job.project_id,
                    question=question,
                    context=context,
                    curation_status="candidate",
                    source_version_id=version.id,
                    extraction_method="llm",
                    model_run_id=model_run.id if model_run is not None else None,
                    confidence=candidate.confidence,
                )
            )
            continue

        existing_question.source_version_id = version.id
        existing_question.extraction_method = "llm"
        existing_question.model_run_id = model_run.id if model_run is not None else None
        existing_question.confidence = candidate.confidence
        if existing_question.curation_status == "candidate":
            existing_question.question = question
            existing_question.context = context

    for decision_row in decision_rows:
        if (
            decision_row.curation_status == "candidate"
            and decision_row.source_version_id == version.id
            and decision_row.extraction_method == "llm"
            and decision_signature(
                decision_row.title,
                decision_row.decision,
                decision_row.consequences,
            )
            not in extracted_decision_signatures
        ):
            await session.delete(decision_row)
    for requirement_row in requirement_rows:
        if (
            requirement_row.curation_status == "candidate"
            and requirement_row.source_version_id == version.id
            and requirement_row.extraction_method == "llm"
            and requirement_signature(
                requirement_row.requirement_id,
                requirement_row.title,
                requirement_row.description,
                requirement_row.priority,
            )
            not in extracted_requirement_signatures
        ):
            await session.delete(requirement_row)
    for question_row in question_rows:
        if (
            question_row.curation_status == "candidate"
            and question_row.source_version_id == version.id
            and question_row.extraction_method == "llm"
            and open_question_signature(question_row.question, question_row.context)
            not in extracted_question_signatures
        ):
            await session.delete(question_row)

    if model_run is not None:
        model_run.items_processed = (model_run.items_processed or 0) + len(candidates)
    await session.flush()


async def _load_latest_version_text(
    session: AsyncSession,
    version_id: UUID,
) -> VersionText | None:
    result = await session.execute(
        select(VersionText)
        .where(
            VersionText.version_id == version_id,
            VersionText.text_kind.in_(["raw", "extracted"]),
        )
        .order_by(VersionText.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _get_or_create_entity(
    session: AsyncSession,
    *,
    entity_type: str,
    canonical_name: str,
    metadata: dict | None = None,
) -> Entity:
    result = await session.execute(
        select(Entity).where(
            Entity.entity_type == entity_type,
            Entity.canonical_name == canonical_name,
        )
    )
    entity = result.scalar_one_or_none()
    extracted_at = datetime.now(UTC)
    if entity is not None:
        entity.last_seen_at = extracted_at
        if metadata and not entity.metadata_:
            entity.metadata_ = metadata
        return entity

    entity = Entity(
        entity_type=entity_type,
        canonical_name=canonical_name,
        metadata_=metadata,
        first_seen_at=extracted_at,
        last_seen_at=extracted_at,
    )
    session.add(entity)
    await session.flush()
    return entity


def _resolve_schema_relationship_entity(
    reference: str,
    entity_map: dict[tuple[str, str], Entity],
) -> Entity | None:
    candidates = [
        ("column", reference),
        ("field", reference),
        ("endpoint", reference),
        ("schema", reference),
        ("model", reference),
        ("table", reference.split(".", 1)[0]),
    ]
    for key in candidates:
        entity = entity_map.get(key)
        if entity is not None:
            return entity
    return None


async def _handle_candidate_job(
    session: AsyncSession,
    job: IngestionJob,
    version: DocumentVersion,
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
    if version_text is None or not version_text.content.strip():
        job.status = "skipped"
        job.error_message = "no extracted text found"
        return

    decision_rows_result = await session.execute(
        select(Decision).where(Decision.project_id == job.project_id)
    )
    decision_rows = decision_rows_result.scalars().all()
    requirement_rows_result = await session.execute(
        select(Requirement).where(Requirement.project_id == job.project_id)
    )
    requirement_rows = requirement_rows_result.scalars().all()
    question_rows_result = await session.execute(
        select(OpenQuestion).where(OpenQuestion.project_id == job.project_id)
    )
    question_rows = question_rows_result.scalars().all()

    decision_by_signature = {
        decision_signature(row.title, row.decision, row.consequences): row
        for row in decision_rows
    }
    requirement_by_signature = {
        requirement_signature(row.requirement_id, row.title, row.description, row.priority): row
        for row in requirement_rows
    }
    question_by_signature = {
        open_question_signature(row.question, row.context): row
        for row in question_rows
    }

    extracted_decision_signatures: set[str] = set()
    extracted_requirement_signatures: set[str] = set()
    extracted_question_signatures: set[str] = set()

    for decision_candidate in extract_decisions_from_adr(version_text.content):
        signature = decision_signature(
            decision_candidate.title,
            decision_candidate.decision,
            decision_candidate.consequences,
        )
        extracted_decision_signatures.add(signature)
        existing_decision = decision_by_signature.get(signature)
        if existing_decision is None:
            session.add(
                Decision(
                    uid=generate_uid("dec"),
                    project_id=job.project_id,
                    title=decision_candidate.title,
                    status=decision_candidate.status or "accepted",
                    context=decision_candidate.context,
                    decision=decision_candidate.decision,
                    consequences=decision_candidate.consequences,
                    curation_status="candidate",
                    source_version_id=version.id,
                    first_seen_version_id=version.id,
                    last_seen_version_id=version.id,
                    extraction_method=decision_candidate.extraction_method,
                    confidence=decision_candidate.confidence,
                )
            )
            continue

        existing_decision.source_version_id = version.id
        existing_decision.last_seen_version_id = version.id
        existing_decision.extraction_method = decision_candidate.extraction_method
        existing_decision.confidence = decision_candidate.confidence
        if existing_decision.curation_status == "candidate":
            existing_decision.title = decision_candidate.title
            existing_decision.status = decision_candidate.status or existing_decision.status
            existing_decision.context = decision_candidate.context
            existing_decision.decision = decision_candidate.decision
            existing_decision.consequences = decision_candidate.consequences

    for requirement_candidate in extract_requirements(version_text.content):
        signature = requirement_signature(
            requirement_candidate.requirement_id,
            requirement_candidate.title,
            requirement_candidate.description,
            requirement_candidate.priority,
        )
        extracted_requirement_signatures.add(signature)
        existing_requirement = requirement_by_signature.get(signature)
        if existing_requirement is None:
            session.add(
                Requirement(
                    uid=generate_uid("req"),
                    project_id=job.project_id,
                    requirement_id=requirement_candidate.requirement_id,
                    title=requirement_candidate.title,
                    description=requirement_candidate.description,
                    priority=requirement_candidate.priority,
                    curation_status="candidate",
                    source_version_id=version.id,
                    first_seen_version_id=version.id,
                    last_seen_version_id=version.id,
                    extraction_method=requirement_candidate.extraction_method,
                    confidence=requirement_candidate.confidence,
                )
            )
            continue

        existing_requirement.source_version_id = version.id
        existing_requirement.last_seen_version_id = version.id
        existing_requirement.extraction_method = requirement_candidate.extraction_method
        existing_requirement.confidence = requirement_candidate.confidence
        if existing_requirement.curation_status == "candidate":
            existing_requirement.requirement_id = requirement_candidate.requirement_id
            existing_requirement.title = requirement_candidate.title
            existing_requirement.description = requirement_candidate.description
            existing_requirement.priority = requirement_candidate.priority

    for question_candidate in extract_open_questions(version_text.content):
        signature = open_question_signature(question_candidate.question, question_candidate.context)
        extracted_question_signatures.add(signature)
        existing_question = question_by_signature.get(signature)
        if existing_question is None:
            session.add(
                OpenQuestion(
                    project_id=job.project_id,
                    question=question_candidate.question,
                    context=question_candidate.context,
                    curation_status="candidate",
                    source_version_id=version.id,
                    extraction_method=question_candidate.extraction_method,
                    confidence=question_candidate.confidence,
                )
            )
            continue

        existing_question.source_version_id = version.id
        existing_question.extraction_method = question_candidate.extraction_method
        existing_question.confidence = question_candidate.confidence
        if existing_question.curation_status == "candidate":
            existing_question.question = question_candidate.question
            existing_question.context = question_candidate.context

    for decision_row in decision_rows:
        if (
            decision_row.curation_status == "candidate"
            and decision_row.source_version_id == version.id
            and decision_signature(
                decision_row.title,
                decision_row.decision,
                decision_row.consequences,
            )
            not in extracted_decision_signatures
        ):
            await session.delete(decision_row)
    for requirement_row in requirement_rows:
        if (
            requirement_row.curation_status == "candidate"
            and requirement_row.source_version_id == version.id
            and requirement_signature(
                requirement_row.requirement_id,
                requirement_row.title,
                requirement_row.description,
                requirement_row.priority,
            )
            not in extracted_requirement_signatures
        ):
            await session.delete(requirement_row)
    for question_row in question_rows:
        if (
            question_row.curation_status == "candidate"
            and question_row.source_version_id == version.id
            and open_question_signature(question_row.question, question_row.context)
            not in extracted_question_signatures
        ):
            await session.delete(question_row)

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


async def _resolve_ner_model_run(
    session: AsyncSession,
    gateway: ModelGateway,
) -> ModelRun | None:
    return await get_active_ner_model_run(session, gateway, create=True)


async def _resolve_llm_model_run(
    session: AsyncSession,
    job: IngestionJob,
    gateway: ModelGateway,
) -> ModelRun | None:
    if job.model_run_id is not None:
        existing = await session.get(ModelRun, job.model_run_id)
        if existing is not None:
            return existing
    return await get_active_llm_model_run(session, gateway, create=True)


def _supports_schema_parse(canonical_path: str) -> bool:
    return Path(canonical_path).suffix.casefold() in {".sql", ".prisma", ".yaml", ".yml", ".json"}


def _match_chunk_for_span(
    chunks: Sequence[DocumentChunk],
    start_char: int,
    end_char: int,
) -> UUID | None:
    best_chunk_id: UUID | None = None
    best_overlap = 0
    for chunk in chunks:
        overlap = min(end_char, chunk.end_char) - max(start_char, chunk.start_char)
        if overlap > best_overlap:
            best_overlap = overlap
            best_chunk_id = chunk.id
    return best_chunk_id


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
