"""LLM-backed relationship extraction."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

VALID_RELATIONSHIP_TYPES = frozenset(
    {"depends_on", "exposes", "uses", "supersedes", "conflicts_with"}
)


@dataclass(slots=True)
class RelationshipCandidate:
    source_entity: str
    target_entity: str
    relationship_type: str
    evidence_text: str
    confidence: float


def build_relationship_prompt(chunk_text: str, known_entities: list[str]) -> str:
    entities = ", ".join(known_entities) if known_entities else "(none provided)"
    return (
        "You are extracting evidence-backed relationships between software-project entities.\n"
        "Return JSON only in the form {\"relationships\": [...]}.\n"
        "Allowed relationship_type values: depends_on, exposes, uses, supersedes, conflicts_with.\n"
        "Only emit relationships that are directly supported by the text.\n\n"
        f"KNOWN ENTITIES:\n{entities}\n\n"
        f"TEXT:\n{chunk_text}\n"
    )


def parse_relationship_response(
    response: str,
    *,
    min_confidence: float = 0.5,
) -> list[RelationshipCandidate]:
    payload = response.strip()
    fence_match = re.search(r"```(?:json)?\s*(.*?)```", payload, re.DOTALL)
    if fence_match:
        payload = fence_match.group(1).strip()

    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError:
        logger.warning("failed to decode relationship extraction response")
        return []

    raw_items = decoded.get("relationships", []) if isinstance(decoded, dict) else []
    candidates: list[RelationshipCandidate] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        source = str(item.get("source_entity", "")).strip()
        target = str(item.get("target_entity", "")).strip()
        relation = str(item.get("relationship_type", "")).strip()
        if not source or not target or relation not in VALID_RELATIONSHIP_TYPES:
            continue
        try:
            confidence = float(item.get("confidence", 0.0))
        except (TypeError, ValueError):
            continue
        if confidence < min_confidence:
            continue
        candidates.append(
            RelationshipCandidate(
                source_entity=source,
                target_entity=target,
                relationship_type=relation,
                evidence_text=str(item.get("evidence_text", "")).strip(),
                confidence=confidence,
            )
        )
    return candidates


async def extract_relationships_llm(
    chunk_text: str,
    known_entities: list[str],
    gateway,
) -> list[RelationshipCandidate]:
    if not getattr(gateway, "llm", None):
        return []

    prompt = build_relationship_prompt(chunk_text, known_entities)
    try:
        response = await gateway.generate(prompt, max_tokens=1200, temperature=0.1)
    except Exception:
        logger.exception("relationship extraction request failed")
        return []
    return parse_relationship_response(response)
