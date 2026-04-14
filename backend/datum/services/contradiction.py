"""Contradiction detection across project intelligence artifacts."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from datum.models.core import Document, DocumentVersion
from datum.models.intelligence import Entity, EntityMention


@dataclass(slots=True)
class ContradictionCandidate:
    insight_type: str
    severity: str
    title: str
    explanation: str
    confidence: float
    evidence: dict[str, Any] = field(default_factory=dict)


def detect_version_conflicts(mentions: list[dict[str, str]]) -> list[ContradictionCandidate]:
    by_entity: dict[str, list[dict[str, str]]] = defaultdict(list)
    for mention in mentions:
        by_entity[mention["entity"]].append(mention)

    candidates: list[ContradictionCandidate] = []
    for entity, entity_mentions in by_entity.items():
        versions = sorted({item["version"] for item in entity_mentions if item.get("version")})
        if len(versions) <= 1:
            continue
        docs = sorted({item["doc"] for item in entity_mentions if item.get("doc")})
        candidates.append(
            ContradictionCandidate(
                insight_type="contradiction",
                severity="warning",
                title=f"Conflicting versions for {entity}: {', '.join(versions)}",
                explanation=(
                    f"{entity} appears with inconsistent versions across project documents."
                ),
                confidence=0.8,
                evidence={"entity": entity, "versions": versions, "documents": docs},
            )
        )
    return candidates


def detect_entity_property_conflicts(
    properties: list[dict[str, str]],
) -> list[ContradictionCandidate]:
    by_key: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for item in properties:
        by_key[(item["entity"], item["property"])].append(item)

    candidates: list[ContradictionCandidate] = []
    for (entity, prop), values in by_key.items():
        distinct_values = sorted({value["value"] for value in values if value.get("value")})
        if len(distinct_values) <= 1:
            continue
        docs = sorted({value["doc"] for value in values if value.get("doc")})
        candidates.append(
            ContradictionCandidate(
                insight_type="contradiction",
                severity="warning",
                title=f"Conflicting {prop} for {entity}: {', '.join(distinct_values)}",
                explanation=f"{entity}.{prop} has conflicting values across project documents.",
                confidence=0.7,
                evidence={
                    "entity": entity,
                    "property": prop,
                    "values": distinct_values,
                    "documents": docs,
                },
            )
        )
    return candidates


async def detect_contradictions_for_project(
    session: AsyncSession,
    project_id,
) -> list[ContradictionCandidate]:
    result = await session.execute(
        select(
            Entity.canonical_name,
            EntityMention.raw_text,
            Document.canonical_path,
        )
        .select_from(EntityMention)
        .join(Entity, EntityMention.entity_id == Entity.id)
        .join(DocumentVersion, EntityMention.version_id == DocumentVersion.id)
        .join(Document, DocumentVersion.document_id == Document.id)
        .where(Document.project_id == project_id)
    )

    version_mentions: list[dict[str, str]] = []
    for canonical_name, raw_text, canonical_path in result.fetchall():
        text = raw_text or ""
        version = _extract_version_token(text)
        if version is None:
            continue
        version_mentions.append(
            {
                "entity": canonical_name,
                "text": text,
                "doc": canonical_path,
                "version": version,
            }
        )

    return detect_version_conflicts(version_mentions)


def _extract_version_token(raw_text: str) -> str | None:
    for token in raw_text.split():
        stripped = token.strip("()[]{}.,;:")
        if not stripped:
            continue
        if stripped[0].isdigit() and any(char.isdigit() for char in stripped):
            return stripped
        if stripped.lower().startswith("v") and len(stripped) > 1 and stripped[1].isdigit():
            return stripped[1:]
    return None
