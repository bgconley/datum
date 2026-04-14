"""LLM-backed extraction for candidate records."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

VALID_CANDIDATE_TYPES = frozenset({"decision", "requirement", "open_question"})


@dataclass(slots=True)
class LLMCandidate:
    candidate_type: str
    title: str
    description: str
    evidence_text: str
    confidence: float


def build_candidate_prompt(chunk_text: str, doc_type: str = "general") -> str:
    return (
        "You are extracting candidate project-memory records from a software document.\n"
        "Return JSON only in the form {\"candidates\": [...]}.\n"
        "Allowed type values: decision, requirement, open_question.\n"
        "Only extract items directly supported by the text.\n\n"
        f"DOCUMENT TYPE: {doc_type}\n\n"
        f"TEXT:\n{chunk_text}\n"
    )


def parse_candidate_response(
    response: str,
    *,
    min_confidence: float = 0.5,
) -> list[LLMCandidate]:
    payload = response.strip()
    fence_match = re.search(r"```(?:json)?\s*(.*?)```", payload, re.DOTALL)
    if fence_match:
        payload = fence_match.group(1).strip()

    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError:
        logger.warning("failed to decode candidate extraction response")
        return []

    raw_items = decoded.get("candidates", []) if isinstance(decoded, dict) else []
    candidates: list[LLMCandidate] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        candidate_type = str(item.get("type", "")).strip()
        title = str(item.get("title", "")).strip()
        if candidate_type not in VALID_CANDIDATE_TYPES or not title:
            continue
        try:
            confidence = float(item.get("confidence", 0.0))
        except (TypeError, ValueError):
            continue
        if confidence < min_confidence:
            continue
        candidates.append(
            LLMCandidate(
                candidate_type=candidate_type,
                title=title,
                description=str(item.get("description", "")).strip(),
                evidence_text=str(item.get("evidence_text", "")).strip(),
                confidence=confidence,
            )
        )
    return candidates


async def extract_candidates_llm(
    chunk_text: str,
    doc_type: str,
    gateway,
) -> list[LLMCandidate]:
    if not getattr(gateway, "llm", None):
        return []

    prompt = build_candidate_prompt(chunk_text, doc_type)
    try:
        response = await gateway.generate(prompt, max_tokens=1600, temperature=0.1)
    except Exception:
        logger.exception("candidate extraction request failed")
        return []
    return parse_candidate_response(response)
