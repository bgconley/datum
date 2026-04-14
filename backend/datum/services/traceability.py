"""Project traceability and insight-query services."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from datum.models.core import Document, DocumentVersion
from datum.models.intelligence import (
    Decision,
    DocumentLink,
    Entity,
    EntityRelationship,
    Insight,
    Requirement,
)
from datum.services.insight_analysis import AnalysisResult, run_insight_analysis
from datum.services.intelligence import get_project_or_404


@dataclass(slots=True)
class DocumentLinkRecord:
    id: str
    source_document_path: str
    target_document_path: str
    link_type: str
    anchor_text: str | None
    auto_detected: bool
    confidence: float | None
    created_at: datetime | None


@dataclass(slots=True)
class EntityRelationshipRecord:
    id: str
    source_entity: str
    target_entity: str
    relationship_type: str
    extraction_method: str
    evidence_text: str | None
    confidence: float | None
    created_at: datetime | None


@dataclass(slots=True)
class InsightRecord:
    id: str
    insight_type: str
    severity: str
    status: str
    title: str
    explanation: str | None
    confidence: float | None
    evidence: dict | None
    created_at: datetime | None
    resolved_at: datetime | None


@dataclass(slots=True)
class TraceabilityNode:
    uid: str | None = None
    title: str | None = None
    status: str | None = None
    description: str | None = None
    priority: str | None = None
    decision: str | None = None
    name: str | None = None
    entity_type: str | None = None


@dataclass(slots=True)
class TraceabilityChain:
    requirement: TraceabilityNode | None
    decisions: list[TraceabilityNode] = field(default_factory=list)
    schema_entities: list[TraceabilityNode] = field(default_factory=list)


async def list_project_links(
    session: AsyncSession,
    slug: str,
    *,
    limit: int = 200,
) -> list[DocumentLinkRecord]:
    project = await get_project_or_404(session, slug)
    source_version = aliased(DocumentVersion)
    source_document = aliased(Document)
    target_document = aliased(Document)

    result = await session.execute(
        select(
            DocumentLink.id,
            source_document.canonical_path,
            target_document.canonical_path,
            DocumentLink.link_type,
            DocumentLink.anchor_text,
            DocumentLink.auto_detected,
            DocumentLink.confidence,
            DocumentLink.created_at,
        )
        .join(source_version, DocumentLink.source_version_id == source_version.id)
        .join(source_document, source_version.document_id == source_document.id)
        .join(target_document, DocumentLink.target_document_id == target_document.id)
        .where(source_document.project_id == project.id)
        .order_by(DocumentLink.created_at.desc().nullslast())
        .limit(limit)
    )
    return [
        DocumentLinkRecord(
            id=str(row[0]),
            source_document_path=row[1],
            target_document_path=row[2],
            link_type=row[3],
            anchor_text=row[4],
            auto_detected=bool(row[5]),
            confidence=row[6],
            created_at=row[7],
        )
        for row in result.fetchall()
    ]


async def list_project_entity_relationships(
    session: AsyncSession,
    slug: str,
    *,
    entity_name: str | None = None,
    relationship_type: str | None = None,
    limit: int = 200,
) -> list[EntityRelationshipRecord]:
    project = await get_project_or_404(session, slug)
    source_entity = aliased(Entity)
    target_entity = aliased(Entity)
    evidence_version = aliased(DocumentVersion)
    evidence_document = aliased(Document)

    query = (
        select(
            EntityRelationship.id,
            source_entity.canonical_name,
            target_entity.canonical_name,
            EntityRelationship.relationship_type,
            EntityRelationship.extraction_method,
            EntityRelationship.evidence_text,
            EntityRelationship.confidence,
            EntityRelationship.created_at,
        )
        .join(source_entity, EntityRelationship.source_entity_id == source_entity.id)
        .join(target_entity, EntityRelationship.target_entity_id == target_entity.id)
        .join(evidence_version, EntityRelationship.evidence_version_id == evidence_version.id)
        .join(evidence_document, evidence_version.document_id == evidence_document.id)
        .where(evidence_document.project_id == project.id)
    )
    if entity_name:
        query = query.where(
            or_(
                source_entity.canonical_name.ilike(f"%{entity_name}%"),
                target_entity.canonical_name.ilike(f"%{entity_name}%"),
            )
        )
    if relationship_type:
        query = query.where(EntityRelationship.relationship_type == relationship_type)

    result = await session.execute(
        query.order_by(EntityRelationship.created_at.desc().nullslast()).limit(limit)
    )
    return [
        EntityRelationshipRecord(
            id=str(row[0]),
            source_entity=row[1],
            target_entity=row[2],
            relationship_type=row[3],
            extraction_method=row[4],
            evidence_text=row[5],
            confidence=row[6],
            created_at=row[7],
        )
        for row in result.fetchall()
    ]


async def list_project_insights(
    session: AsyncSession,
    slug: str,
    *,
    status: str | None = None,
    limit: int = 100,
) -> list[InsightRecord]:
    project = await get_project_or_404(session, slug)
    query = select(Insight).where(Insight.project_id == project.id)
    if status:
        query = query.where(Insight.status == status)
    result = await session.execute(
        query.order_by(Insight.created_at.desc().nullslast()).limit(limit)
    )
    return [
        InsightRecord(
            id=str(insight.id),
            insight_type=insight.insight_type,
            severity=insight.severity,
            status=insight.status,
            title=insight.title,
            explanation=insight.explanation,
            confidence=insight.confidence,
            evidence=insight.evidence,
            created_at=insight.created_at,
            resolved_at=insight.resolved_at,
        )
        for insight in result.scalars().all()
    ]


async def analyze_project_insights(
    session: AsyncSession,
    slug: str,
    *,
    max_age_days: int = 60,
) -> AnalysisResult:
    project = await get_project_or_404(session, slug)
    result = await run_insight_analysis(session, project.id, max_age_days=max_age_days)
    await session.commit()
    return result


async def update_project_insight_status(
    session: AsyncSession,
    slug: str,
    *,
    insight_id: str,
    status: str,
) -> InsightRecord:
    valid_statuses = {"acknowledged", "dismissed", "resolved", "false_positive"}
    if status not in valid_statuses:
        raise ValueError(
            "Invalid status. Must be one of: acknowledged, dismissed, resolved, false_positive"
        )

    project = await get_project_or_404(session, slug)
    insight = await session.get(Insight, UUID(insight_id))
    if insight is None or insight.project_id != project.id:
        raise ValueError("Insight not found")

    insight.status = status
    insight.resolved_at = (
        datetime.now(UTC) if status in {"resolved", "false_positive"} else None
    )
    await session.commit()
    await session.refresh(insight)
    return InsightRecord(
        id=str(insight.id),
        insight_type=insight.insight_type,
        severity=insight.severity,
        status=insight.status,
        title=insight.title,
        explanation=insight.explanation,
        confidence=insight.confidence,
        evidence=insight.evidence,
        created_at=insight.created_at,
        resolved_at=insight.resolved_at,
    )


async def get_traceability_chains(
    session: AsyncSession,
    slug: str,
) -> list[TraceabilityChain]:
    project = await get_project_or_404(session, slug)
    requirement_result = await session.execute(
        select(Requirement)
        .where(
            Requirement.project_id == project.id,
            Requirement.curation_status == "accepted",
        )
        .order_by(Requirement.created_at.asc().nullslast())
    )
    requirements = requirement_result.scalars().all()

    target_document = aliased(Document)
    decision_source_version = aliased(DocumentVersion)

    chains: list[TraceabilityChain] = []
    schema_types = {"table", "column", "model", "field", "endpoint", "schema"}

    for requirement in requirements:
        decision_query = (
            select(Decision, target_document.canonical_path)
            .join(decision_source_version, Decision.source_version_id == decision_source_version.id)
            .join(target_document, decision_source_version.document_id == target_document.id)
            .where(
                Decision.project_id == project.id,
                Decision.curation_status == "accepted",
            )
        )
        if requirement.source_version_id is not None:
            decision_query = decision_query.where(
                or_(
                    Decision.source_version_id == requirement.source_version_id,
                    target_document.id.in_(
                        select(DocumentLink.target_document_id)
                        .where(DocumentLink.source_version_id == requirement.source_version_id)
                    ),
                )
            )

        decision_rows = (await session.execute(decision_query)).all()
        decision_nodes = [
            TraceabilityNode(
                uid=decision.uid,
                title=decision.title,
                status=decision.status,
                decision=decision.decision,
                description=document_path,
            )
            for decision, document_path in decision_rows
        ]

        decision_version_ids = [
            decision.source_version_id
            for decision, _document_path in decision_rows
            if decision.source_version_id is not None
        ]
        schema_nodes: dict[tuple[str | None, str | None], TraceabilityNode] = {}
        if decision_version_ids:
            linked_schema_version_rows = (
                await session.execute(
                    select(DocumentLink.target_version_id, Document.current_version_id)
                    .join(Document, DocumentLink.target_document_id == Document.id)
                    .where(DocumentLink.source_version_id.in_(decision_version_ids))
                )
            ).all()
            relationship_version_ids = set(decision_version_ids)
            for target_version_id, current_version_id in linked_schema_version_rows:
                if target_version_id is not None:
                    relationship_version_ids.add(target_version_id)
                elif current_version_id is not None:
                    relationship_version_ids.add(current_version_id)

            source_entity = aliased(Entity)
            target_entity = aliased(Entity)
            relationship_rows = (
                await session.execute(
                    select(
                        source_entity.canonical_name,
                        source_entity.entity_type,
                        target_entity.canonical_name,
                        target_entity.entity_type,
                    )
                    .select_from(EntityRelationship)
                    .join(
                        source_entity,
                        EntityRelationship.source_entity_id == source_entity.id,
                    )
                    .join(
                        target_entity,
                        EntityRelationship.target_entity_id == target_entity.id,
                    )
                    .where(
                        EntityRelationship.evidence_version_id.in_(relationship_version_ids)
                    )
                )
            ).all()
            for source_name, source_type, target_name, target_type in relationship_rows:
                if source_type in schema_types:
                    schema_nodes[(source_name, source_type)] = TraceabilityNode(
                        name=source_name,
                        entity_type=source_type,
                    )
                if target_type in schema_types:
                    schema_nodes[(target_name, target_type)] = TraceabilityNode(
                        name=target_name,
                        entity_type=target_type,
                    )

        chains.append(
            TraceabilityChain(
                requirement=TraceabilityNode(
                    uid=requirement.uid,
                    title=requirement.title,
                    status=requirement.status,
                    description=requirement.description,
                    priority=requirement.priority,
                ),
                decisions=decision_nodes,
                schema_entities=list(schema_nodes.values()),
            )
        )

    return chains
