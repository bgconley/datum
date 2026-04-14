"""Reusable intelligence-layer services for Phase 5 and future agent APIs."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

import yaml
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from datum.models.core import Document, DocumentVersion, Project
from datum.models.intelligence import Decision, Entity, EntityMention, OpenQuestion, Requirement
from datum.schemas.inbox import AcceptCandidateRequest
from datum.services.db_sync import log_audit_event
from datum.services.filesystem import atomic_write, generate_uid

CandidateType = Literal["decision", "requirement", "open_question"]


@dataclass(slots=True)
class CandidateRecord:
    id: str
    candidate_type: CandidateType
    title: str
    context: str | None
    severity: Literal["high", "medium", "low"]
    decision: str | None = None
    consequences: str | None = None
    description: str | None = None
    priority: str | None = None
    resolution: str | None = None
    curation_status: str = "candidate"
    extraction_method: str | None = None
    confidence: float | None = None
    source_doc_path: str | None = None
    source_version: int | None = None
    created_at: str | None = None


@dataclass(slots=True)
class CandidateAction:
    id: str
    curation_status: str
    canonical_record_path: str | None = None


@dataclass(slots=True)
class EntitySummary:
    entity_type: str
    canonical_name: str
    count: int


@dataclass(slots=True)
class OpenQuestionSummary:
    id: str
    question: str
    context: str | None
    age_days: int
    is_stale: bool
    source_doc_path: str | None = None
    source_version: int | None = None
    canonical_record_path: str | None = None
    created_at: str | None = None


@dataclass(slots=True)
class ProjectIntelligenceSummary:
    pending_candidate_count: int
    key_entities: list[EntitySummary]
    open_questions: list[OpenQuestionSummary]


def decision_signature(title: str, decision_text: str | None, consequences: str | None) -> str:
    payload = f"{title}\n{decision_text or ''}\n{consequences or ''}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def requirement_signature(
    requirement_id: str | None,
    title: str,
    description: str | None,
    priority: str | None,
) -> str:
    payload = f"{requirement_id or ''}\n{title}\n{description or ''}\n{priority or ''}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def open_question_signature(question: str, context: str | None) -> str:
    payload = f"{question}\n{context or ''}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def candidate_severity(
    candidate_type: CandidateType,
    extraction_method: str | None,
) -> Literal["high", "medium", "low"]:
    if candidate_type in {"decision", "requirement"}:
        return "high"
    if extraction_method == "regex_todo_marker":
        return "low"
    return "medium"


async def get_project_or_404(session: AsyncSession, slug: str) -> Project:
    result = await session.execute(select(Project).where(Project.slug == slug))
    project = result.scalar_one_or_none()
    if project is None:
        raise ValueError(f"Project '{slug}' not found")
    return project


async def list_candidates(session: AsyncSession, slug: str) -> list[CandidateRecord]:
    project = await get_project_or_404(session, slug)
    source_info = await _source_info_map(session, project.id)
    candidates: list[CandidateRecord] = []
    candidates.extend(await _list_decision_candidates(session, project, source_info))
    candidates.extend(await _list_requirement_candidates(session, project, source_info))
    candidates.extend(await _list_open_question_candidates(session, project, source_info))
    candidates.sort(key=lambda candidate: candidate.confidence or 0.0, reverse=True)
    return candidates


async def accept_candidate(
    session: AsyncSession,
    *,
    slug: str,
    candidate_type: CandidateType,
    candidate_id: str,
    body: AcceptCandidateRequest,
    actor_type: str = "web",
    actor_name: str | None = "inbox",
    request_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> CandidateAction:
    project = await get_project_or_404(session, slug)
    project_path = Path(project.filesystem_path)

    if candidate_type == "decision":
        row = await session.get(Decision, UUID(candidate_id))
        if row is None or row.project_id != project.id:
            raise ValueError("Decision candidate not found")

        was_edited = False
        if body.title is not None:
            was_edited = was_edited or body.title != row.title
            row.title = body.title
        if body.context is not None:
            was_edited = was_edited or body.context != row.context
            row.context = body.context
        if body.decision is not None:
            was_edited = was_edited or body.decision != row.decision
            row.decision = body.decision
        if body.consequences is not None:
            was_edited = was_edited or body.consequences != row.consequences
            row.consequences = body.consequences

        record_path = project_path / ".piq" / "records" / "decisions" / f"{row.uid}.yaml"
        record_payload = {
            "uid": row.uid,
            "title": row.title,
            "status": row.status,
            "context": row.context,
            "decision": row.decision,
            "consequences": row.consequences,
            "source_version_id": str(row.source_version_id) if row.source_version_id else None,
            "extraction_method": row.extraction_method,
            "confidence": row.confidence,
        }
        record_bytes = yaml.safe_dump(
            {key: value for key, value in record_payload.items() if value is not None},
            sort_keys=False,
        ).encode("utf-8")
        atomic_write(record_path, record_bytes)
        row.curation_status = "edited" if was_edited else "accepted"
        row.canonical_record_path = record_path.relative_to(project_path).as_posix()
        row.record_hash = f"sha256:{hashlib.sha256(record_bytes).hexdigest()}"
        row.valid_from = row.valid_from or datetime.now(UTC)
        await log_audit_event(
            session,
            actor_type=actor_type,
            actor_name=actor_name,
            operation="accept_candidate",
            project_id=project.id,
            target_path=row.canonical_record_path,
            new_hash=row.record_hash,
            request_id=request_id,
            metadata=metadata,
        )
        await session.commit()
        return CandidateAction(
            id=str(row.id),
            curation_status=row.curation_status,
            canonical_record_path=row.canonical_record_path,
        )

    if candidate_type == "requirement":
        requirement_row = await session.get(Requirement, UUID(candidate_id))
        if requirement_row is None or requirement_row.project_id != project.id:
            raise ValueError("Requirement candidate not found")

        was_edited = False
        if body.title is not None:
            was_edited = was_edited or body.title != requirement_row.title
            requirement_row.title = body.title
        if body.context is not None and body.description is None:
            was_edited = was_edited or body.context != requirement_row.description
            requirement_row.description = body.context
        if body.description is not None:
            was_edited = was_edited or body.description != requirement_row.description
            requirement_row.description = body.description
        if body.priority is not None:
            was_edited = was_edited or body.priority != requirement_row.priority
            requirement_row.priority = body.priority

        record_path = (
            project_path / ".piq" / "records" / "requirements" / f"{requirement_row.uid}.yaml"
        )
        record_payload = {
            "uid": requirement_row.uid,
            "requirement_id": requirement_row.requirement_id,
            "title": requirement_row.title,
            "description": requirement_row.description,
            "priority": requirement_row.priority,
            "status": requirement_row.status,
            "source_version_id": (
                str(requirement_row.source_version_id)
                if requirement_row.source_version_id
                else None
            ),
            "extraction_method": requirement_row.extraction_method,
            "confidence": requirement_row.confidence,
        }
        record_bytes = yaml.safe_dump(
            {key: value for key, value in record_payload.items() if value is not None},
            sort_keys=False,
        ).encode("utf-8")
        atomic_write(record_path, record_bytes)
        requirement_row.curation_status = "edited" if was_edited else "accepted"
        requirement_row.canonical_record_path = record_path.relative_to(project_path).as_posix()
        requirement_row.record_hash = f"sha256:{hashlib.sha256(record_bytes).hexdigest()}"
        requirement_row.valid_from = requirement_row.valid_from or datetime.now(UTC)
        await log_audit_event(
            session,
            actor_type=actor_type,
            actor_name=actor_name,
            operation="accept_candidate",
            project_id=project.id,
            target_path=requirement_row.canonical_record_path,
            new_hash=requirement_row.record_hash,
            request_id=request_id,
            metadata=metadata,
        )
        await session.commit()
        return CandidateAction(
            id=str(requirement_row.id),
            curation_status=requirement_row.curation_status,
            canonical_record_path=requirement_row.canonical_record_path,
        )

    question_row = await session.get(OpenQuestion, UUID(candidate_id))
    if question_row is None or question_row.project_id != project.id:
        raise ValueError("Open question candidate not found")

    was_edited = False
    if body.title is not None:
        was_edited = was_edited or body.title != question_row.question
        question_row.question = body.title
    if body.context is not None:
        was_edited = was_edited or body.context != question_row.context
        question_row.context = body.context
    if body.resolution is not None:
        was_edited = was_edited or body.resolution != question_row.resolution
        question_row.resolution = body.resolution

    record_uid = generate_uid("oq")
    record_path = project_path / ".piq" / "records" / "open-questions" / f"{record_uid}.yaml"
    record_payload = {
        "uid": record_uid,
        "question": question_row.question,
        "context": question_row.context,
        "status": question_row.status,
        "resolution": question_row.resolution,
        "source_version_id": (
            str(question_row.source_version_id) if question_row.source_version_id else None
        ),
        "extraction_method": question_row.extraction_method,
        "confidence": question_row.confidence,
    }
    record_bytes = yaml.safe_dump(
        {key: value for key, value in record_payload.items() if value is not None},
        sort_keys=False,
    ).encode("utf-8")
    atomic_write(record_path, record_bytes)
    question_row.curation_status = "edited" if was_edited else "accepted"
    question_row.canonical_record_path = record_path.relative_to(project_path).as_posix()
    await log_audit_event(
        session,
        actor_type=actor_type,
        actor_name=actor_name,
        operation="accept_candidate",
        project_id=project.id,
        target_path=question_row.canonical_record_path,
        new_hash=f"sha256:{hashlib.sha256(record_bytes).hexdigest()}",
        request_id=request_id,
        metadata=metadata,
    )
    await session.commit()
    return CandidateAction(
        id=str(question_row.id),
        curation_status=question_row.curation_status,
        canonical_record_path=question_row.canonical_record_path,
    )


async def reject_candidate(
    session: AsyncSession,
    *,
    slug: str,
    candidate_type: CandidateType,
    candidate_id: str,
    actor_type: str = "web",
    actor_name: str | None = "inbox",
    request_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> CandidateAction:
    project = await get_project_or_404(session, slug)
    table_map: dict[CandidateType, type[Any]] = {
        "decision": Decision,
        "requirement": Requirement,
        "open_question": OpenQuestion,
    }
    row = await session.get(table_map[candidate_type], UUID(candidate_id))
    if row is None or row.project_id != project.id:
        raise ValueError("Candidate not found")

    row.curation_status = "rejected"
    await log_audit_event(
        session,
        actor_type=actor_type,
        actor_name=actor_name,
        operation="reject_candidate",
        project_id=project.id,
        target_path=getattr(row, "canonical_record_path", None),
        request_id=request_id,
        metadata=metadata,
    )
    await session.commit()
    return CandidateAction(id=str(row.id), curation_status=row.curation_status)


async def get_project_intelligence_summary(
    session: AsyncSession,
    slug: str,
    *,
    entity_limit: int = 10,
    open_question_limit: int = 5,
) -> ProjectIntelligenceSummary:
    project = await get_project_or_404(session, slug)
    source_info = await _source_info_map(session, project.id)
    pending_candidate_count = 0
    for table in (Decision, Requirement, OpenQuestion):
        result = await session.execute(
            select(func.count())
            .select_from(table)
            .where(table.project_id == project.id, table.curation_status == "candidate")
        )
        pending_candidate_count += int(result.scalar_one() or 0)

    entities_result = await session.execute(
        select(
            Entity.entity_type,
            Entity.canonical_name,
            func.count(EntityMention.id).label("mention_count"),
        )
        .join(EntityMention, EntityMention.entity_id == Entity.id)
        .join(DocumentVersion, EntityMention.version_id == DocumentVersion.id)
        .join(Document, DocumentVersion.document_id == Document.id)
        .where(Document.project_id == project.id)
        .group_by(Entity.entity_type, Entity.canonical_name)
        .order_by(func.count(EntityMention.id).desc(), Entity.canonical_name.asc())
        .limit(entity_limit)
    )
    key_entities = [
        EntitySummary(entity_type=row[0], canonical_name=row[1], count=int(row[2]))
        for row in entities_result.fetchall()
    ]
    open_questions = await _list_curated_open_questions(
        session,
        project,
        source_info,
        limit=open_question_limit,
    )
    return ProjectIntelligenceSummary(
        pending_candidate_count=pending_candidate_count,
        key_entities=key_entities,
        open_questions=open_questions,
    )


async def _list_decision_candidates(
    session: AsyncSession,
    project: Project,
    source_info: dict[UUID, tuple[str | None, int | None]],
) -> list[CandidateRecord]:
    result = await session.execute(
        select(Decision)
        .where(Decision.project_id == project.id, Decision.curation_status == "candidate")
        .order_by(Decision.confidence.desc().nullslast(), Decision.created_at.desc().nullslast())
    )
    rows = result.scalars().all()
    return [
        CandidateRecord(
            id=str(row.id),
            candidate_type="decision",
            title=row.title,
            context=row.context,
            decision=row.decision,
            consequences=row.consequences,
            severity=candidate_severity("decision", row.extraction_method),
            curation_status=row.curation_status,
            extraction_method=row.extraction_method,
            confidence=row.confidence,
            source_doc_path=(
                source_info[row.source_version_id][0]
                if row.source_version_id in source_info
                else None
            ),
            source_version=(
                source_info[row.source_version_id][1]
                if row.source_version_id in source_info
                else None
            ),
            created_at=row.created_at.isoformat() if row.created_at else None,
        )
        for row in rows
    ]


async def _list_requirement_candidates(
    session: AsyncSession,
    project: Project,
    source_info: dict[UUID, tuple[str | None, int | None]],
) -> list[CandidateRecord]:
    result = await session.execute(
        select(Requirement)
        .where(Requirement.project_id == project.id, Requirement.curation_status == "candidate")
        .order_by(
            Requirement.confidence.desc().nullslast(),
            Requirement.created_at.desc().nullslast(),
        )
    )
    rows = result.scalars().all()
    return [
        CandidateRecord(
            id=str(row.id),
            candidate_type="requirement",
            title=row.title,
            context=row.description,
            description=row.description,
            priority=row.priority,
            severity=candidate_severity("requirement", row.extraction_method),
            curation_status=row.curation_status,
            extraction_method=row.extraction_method,
            confidence=row.confidence,
            source_doc_path=(
                source_info[row.source_version_id][0]
                if row.source_version_id in source_info
                else None
            ),
            source_version=(
                source_info[row.source_version_id][1]
                if row.source_version_id in source_info
                else None
            ),
            created_at=row.created_at.isoformat() if row.created_at else None,
        )
        for row in rows
    ]


async def _list_open_question_candidates(
    session: AsyncSession,
    project: Project,
    source_info: dict[UUID, tuple[str | None, int | None]],
) -> list[CandidateRecord]:
    result = await session.execute(
        select(OpenQuestion)
        .where(OpenQuestion.project_id == project.id, OpenQuestion.curation_status == "candidate")
        .order_by(
            OpenQuestion.confidence.desc().nullslast(),
            OpenQuestion.created_at.desc().nullslast(),
        )
    )
    rows = result.scalars().all()
    return [
        CandidateRecord(
            id=str(row.id),
            candidate_type="open_question",
            title=row.question,
            context=row.context,
            resolution=row.resolution,
            severity=candidate_severity("open_question", row.extraction_method),
            curation_status=row.curation_status,
            extraction_method=row.extraction_method,
            confidence=row.confidence,
            source_doc_path=(
                source_info[row.source_version_id][0]
                if row.source_version_id in source_info
                else None
            ),
            source_version=(
                source_info[row.source_version_id][1]
                if row.source_version_id in source_info
                else None
            ),
            created_at=row.created_at.isoformat() if row.created_at else None,
        )
        for row in rows
    ]


async def _list_curated_open_questions(
    session: AsyncSession,
    project: Project,
    source_info: dict[UUID, tuple[str | None, int | None]],
    *,
    limit: int,
) -> list[OpenQuestionSummary]:
    result = await session.execute(
        select(OpenQuestion)
        .where(
            OpenQuestion.project_id == project.id,
            OpenQuestion.status == "open",
            OpenQuestion.curation_status.in_(["accepted", "edited"]),
        )
        .order_by(OpenQuestion.created_at.asc().nullslast(), OpenQuestion.question.asc())
        .limit(limit)
    )
    rows = result.scalars().all()
    now = datetime.now(UTC)
    summaries: list[OpenQuestionSummary] = []
    for row in rows:
        created_at = row.created_at
        if created_at is None:
            age_days = 0
        else:
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=UTC)
            age_days = max((now - created_at).days, 0)
        summaries.append(
            OpenQuestionSummary(
                id=str(row.id),
                question=row.question,
                context=row.context,
                age_days=age_days,
                is_stale=age_days >= 30,
                source_doc_path=(
                    source_info[row.source_version_id][0]
                    if row.source_version_id in source_info
                    else None
                ),
                source_version=(
                    source_info[row.source_version_id][1]
                    if row.source_version_id in source_info
                    else None
                ),
                canonical_record_path=row.canonical_record_path,
                created_at=row.created_at.isoformat() if row.created_at else None,
            )
        )
    return summaries


async def _source_info_map(
    session: AsyncSession,
    project_id: UUID,
) -> dict[UUID, tuple[str | None, int | None]]:
    version_ids: set[UUID] = set()
    for model in (Decision, Requirement, OpenQuestion):
        result = await session.execute(
            select(model.source_version_id).where(model.project_id == project_id)
        )
        version_ids.update(
            version_id for version_id in result.scalars().all() if version_id is not None
        )

    if not version_ids:
        return {}

    source_info: dict[UUID, tuple[str | None, int | None]] = {}
    for version_id in version_ids:
        version = await session.get(DocumentVersion, version_id)
        if version is None:
            continue
        document = await session.get(Document, version.document_id)
        source_info[version_id] = (
            document.canonical_path if document is not None else None,
            version.version_number,
        )
    return source_info
