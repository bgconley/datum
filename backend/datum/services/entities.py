"""Entity listing and detail services."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from datum.models.core import Document, DocumentVersion
from datum.models.intelligence import Entity, EntityMention, EntityRelationship
from datum.services.intelligence import get_project_or_404


@dataclass(slots=True)
class EntitySummaryRecord:
    id: str
    entity_type: str
    canonical_name: str
    mention_count: int


@dataclass(slots=True)
class EntityMentionRecord:
    document_path: str
    document_title: str | None
    chunk_content_snippet: str
    start_char: int
    end_char: int
    confidence: float
    version_number: int | None


@dataclass(slots=True)
class EntityRelationshipDetailRecord:
    related_entity: str
    relationship_type: str
    direction: str
    evidence_text: str | None


@dataclass(slots=True)
class EntityDetailRecord:
    id: str
    entity_type: str
    canonical_name: str
    mentions: list[EntityMentionRecord] = field(default_factory=list)
    relationships: list[EntityRelationshipDetailRecord] = field(default_factory=list)
    mention_count: int = 0


async def list_project_entities(
    session: AsyncSession,
    slug: str,
    *,
    entity_type: str | None = None,
    limit: int = 100,
) -> list[EntitySummaryRecord]:
    project = await get_project_or_404(session, slug)
    mentioned_entity_ids = (
        select(EntityMention.entity_id)
        .join(DocumentVersion, EntityMention.version_id == DocumentVersion.id)
        .join(Document, DocumentVersion.document_id == Document.id)
        .where(Document.project_id == project.id)
    )
    relationship_entity_ids = (
        select(EntityRelationship.source_entity_id)
        .join(DocumentVersion, EntityRelationship.evidence_version_id == DocumentVersion.id)
        .join(Document, DocumentVersion.document_id == Document.id)
        .where(Document.project_id == project.id)
        .union(
            select(EntityRelationship.target_entity_id)
            .join(DocumentVersion, EntityRelationship.evidence_version_id == DocumentVersion.id)
            .join(Document, DocumentVersion.document_id == Document.id)
            .where(Document.project_id == project.id)
        )
    )

    query = (
        select(
            Entity.id,
            Entity.entity_type,
            Entity.canonical_name,
            func.count(EntityMention.id).label("mention_count"),
        )
        .outerjoin(EntityMention, EntityMention.entity_id == Entity.id)
        .outerjoin(DocumentVersion, EntityMention.version_id == DocumentVersion.id)
        .outerjoin(Document, DocumentVersion.document_id == Document.id)
        .where(
            Entity.id.in_(mentioned_entity_ids.union(relationship_entity_ids)),
            or_(Document.project_id == project.id, Document.project_id.is_(None)),
        )
        .group_by(Entity.id, Entity.entity_type, Entity.canonical_name)
        .order_by(func.count(EntityMention.id).desc(), Entity.canonical_name.asc())
        .limit(limit)
    )
    if entity_type:
        query = query.where(Entity.entity_type == entity_type)

    result = await session.execute(query)
    return [
        EntitySummaryRecord(
            id=str(row[0]),
            entity_type=row[1],
            canonical_name=row[2],
            mention_count=int(row[3] or 0),
        )
        for row in result.fetchall()
    ]


async def get_project_entity_detail(
    session: AsyncSession,
    slug: str,
    *,
    entity_id: str,
) -> EntityDetailRecord:
    project = await get_project_or_404(session, slug)
    entity = await session.get(Entity, entity_id)
    if entity is None:
        raise ValueError("Entity not found")

    mention_rows = (
        await session.execute(
            select(
                Document.canonical_path,
                Document.title,
                EntityMention.raw_text,
                EntityMention.text_start_char,
                EntityMention.text_end_char,
                EntityMention.confidence,
                DocumentVersion.version_number,
            )
            .join(DocumentVersion, EntityMention.version_id == DocumentVersion.id)
            .join(Document, DocumentVersion.document_id == Document.id)
            .where(
                EntityMention.entity_id == entity.id,
                Document.project_id == project.id,
            )
            .order_by(Document.canonical_path.asc(), DocumentVersion.version_number.desc())
        )
    ).all()

    source_entity = aliased(Entity)
    target_entity = aliased(Entity)
    evidence_version = aliased(DocumentVersion)
    evidence_document = aliased(Document)
    outgoing_rows = (
        await session.execute(
            select(
                target_entity.canonical_name,
                EntityRelationship.relationship_type,
                EntityRelationship.evidence_text,
            )
            .join(target_entity, EntityRelationship.target_entity_id == target_entity.id)
            .join(evidence_version, EntityRelationship.evidence_version_id == evidence_version.id)
            .join(evidence_document, evidence_version.document_id == evidence_document.id)
            .where(
                EntityRelationship.source_entity_id == entity.id,
                evidence_document.project_id == project.id,
            )
        )
    ).all()
    incoming_rows = (
        await session.execute(
            select(
                source_entity.canonical_name,
                EntityRelationship.relationship_type,
                EntityRelationship.evidence_text,
            )
            .join(source_entity, EntityRelationship.source_entity_id == source_entity.id)
            .join(evidence_version, EntityRelationship.evidence_version_id == evidence_version.id)
            .join(evidence_document, evidence_version.document_id == evidence_document.id)
            .where(
                EntityRelationship.target_entity_id == entity.id,
                evidence_document.project_id == project.id,
            )
        )
    ).all()

    if not mention_rows and not outgoing_rows and not incoming_rows:
        raise ValueError("Entity not found in this project")

    mentions = [
        EntityMentionRecord(
            document_path=row[0],
            document_title=row[1],
            chunk_content_snippet=(row[2] or "")[:240],
            start_char=row[3],
            end_char=row[4],
            confidence=float(row[5] or 0.0),
            version_number=row[6],
        )
        for row in mention_rows
    ]
    relationships = [
        EntityRelationshipDetailRecord(
            related_entity=row[0],
            relationship_type=row[1],
            direction="outgoing",
            evidence_text=row[2],
        )
        for row in outgoing_rows
    ]
    relationships.extend(
        EntityRelationshipDetailRecord(
            related_entity=row[0],
            relationship_type=row[1],
            direction="incoming",
            evidence_text=row[2],
        )
        for row in incoming_rows
    )

    return EntityDetailRecord(
        id=str(entity.id),
        entity_type=entity.entity_type,
        canonical_name=entity.canonical_name,
        mentions=mentions,
        relationships=relationships,
        mention_count=len(mentions),
    )
