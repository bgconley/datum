"""Semantic entity extraction via GLiNER."""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

ENTITY_LABELS: tuple[str, ...] = (
    "technology",
    "programming language",
    "framework",
    "database",
    "service",
    "person",
    "team",
    "date",
    "architecture component",
    "api endpoint",
    "cloud service",
)

_TRAILING_PUNCTUATION = re.compile(r"[\s\.,;:!?]+$")
_LEADING_PUNCTUATION = re.compile(r"^[\s\.,;:!?]+")
_CANONICAL_OVERRIDES = {
    "postgres": "postgresql",
    "postgre": "postgresql",
    "postgresql": "postgresql",
    "k8s": "kubernetes",
}
_HEURISTIC_ENTITY_ALIASES: dict[str, tuple[str, str]] = {
    "postgres": ("postgresql", "technology"),
    "postgresql": ("postgresql", "technology"),
    "redis": ("redis", "technology"),
    "paradedb": ("paradedb", "technology"),
    "pgvector": ("pgvector", "technology"),
    "fastapi": ("fastapi", "technology"),
    "react": ("react", "technology"),
    "tanstack": ("tanstack", "technology"),
    "tanstack router": ("tanstack router", "technology"),
    "codemirror": ("codemirror", "technology"),
    "docker": ("docker", "technology"),
    "caddy": ("caddy", "technology"),
    "alembic": ("alembic", "technology"),
    "kubernetes": ("kubernetes", "technology"),
    "k8s": ("kubernetes", "technology"),
    "python": ("python", "technology"),
    "typescript": ("typescript", "technology"),
    "javascript": ("javascript", "technology"),
    "zfs": ("zfs", "technology"),
    "gliner": ("gliner", "technology"),
    "qwen": ("qwen", "technology"),
    "qwen3": ("qwen3", "technology"),
    "pytorch": ("pytorch", "technology"),
    "mlx": ("mlx", "technology"),
    "vllm": ("vllm", "technology"),
}
_HEURISTIC_ENTITY_RE = re.compile(
    "|".join(
        rf"(?<!\w){re.escape(alias)}(?!\w)"
        for alias in sorted(_HEURISTIC_ENTITY_ALIASES, key=len, reverse=True)
    ),
    re.IGNORECASE,
)
_DATE_ENTITY_RE = re.compile(
    r"\b(?:\d{4}-\d{2}-\d{2}|"
    r"(?:jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|sept|september|oct|october|nov|november|dec|december)"
    r"\s+\d{1,2},\s+\d{4})\b",
    re.IGNORECASE,
)


@dataclass(slots=True)
class EntityCandidate:
    canonical_name: str
    raw_text: str
    entity_type: str
    start_char: int
    end_char: int
    confidence: float
    extraction_method: str = "gliner"


def normalize_entity_name(name: str) -> str:
    cleaned = _TRAILING_PUNCTUATION.sub("", _LEADING_PUNCTUATION.sub("", name))
    lowered = cleaned.casefold()
    return _CANONICAL_OVERRIDES.get(lowered, lowered)


def _parse_entities(raw_entities: Sequence[dict[str, Any]]) -> list[EntityCandidate]:
    candidates: list[EntityCandidate] = []
    seen_spans: set[tuple[int, int, str]] = set()

    for entity in raw_entities:
        start_char = int(entity["start"])
        end_char = int(entity["end"])
        entity_type = str(entity["label"]).strip().casefold()
        raw_text = str(entity["text"]).strip()
        if start_char >= end_char or not raw_text or not entity_type:
            continue

        key = (start_char, end_char, entity_type)
        if key in seen_spans:
            continue
        seen_spans.add(key)

        canonical_name = normalize_entity_name(raw_text)
        if not canonical_name:
            continue

        candidates.append(
            EntityCandidate(
                canonical_name=canonical_name,
                raw_text=raw_text,
                entity_type=entity_type,
                start_char=start_char,
                end_char=end_char,
                confidence=float(entity.get("score", 0.0)),
            )
        )

    return sorted(candidates, key=lambda candidate: (candidate.start_char, candidate.end_char))


def _extract_heuristic_entities(text: str) -> list[EntityCandidate]:
    candidates: list[EntityCandidate] = []
    seen_spans: set[tuple[int, int, str]] = set()

    for match in _HEURISTIC_ENTITY_RE.finditer(text):
        raw_text = match.group(0)
        canonical_key = raw_text.casefold()
        canonical_name, entity_type = _HEURISTIC_ENTITY_ALIASES[canonical_key]
        key = (match.start(), match.end(), entity_type)
        if key in seen_spans or _is_in_code_block(text, match.start()):
            continue
        seen_spans.add(key)
        candidates.append(
            EntityCandidate(
                canonical_name=canonical_name,
                raw_text=raw_text,
                entity_type=entity_type,
                start_char=match.start(),
                end_char=match.end(),
                confidence=0.65,
                extraction_method="heuristic_technical",
            )
        )

    for match in _DATE_ENTITY_RE.finditer(text):
        key = (match.start(), match.end(), "date")
        if key in seen_spans or _is_in_code_block(text, match.start()):
            continue
        seen_spans.add(key)
        candidates.append(
            EntityCandidate(
                canonical_name=match.group(0).casefold(),
                raw_text=match.group(0),
                entity_type="date",
                start_char=match.start(),
                end_char=match.end(),
                confidence=0.6,
                extraction_method="heuristic_date",
            )
        )

    return sorted(candidates, key=lambda candidate: (candidate.start_char, candidate.end_char))


async def extract_entities_gliner(
    text: str,
    *,
    endpoint: str,
    labels: Sequence[str] = ENTITY_LABELS,
    threshold: float = 0.5,
    client: httpx.AsyncClient | None = None,
) -> list[EntityCandidate]:
    if not text.strip():
        return []

    should_close = False
    if client is None:
        client = httpx.AsyncClient(timeout=30.0)
        should_close = True

    try:
        response = await client.post(
            f"{endpoint}/extract",
            json={
                "text": text,
                "labels": list(labels),
                "threshold": threshold,
            },
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            logger.warning(
                "GLiNER extraction returned non-list payload: %s",
                type(payload).__name__,
            )
            return []
        extracted = _parse_entities(payload)
        return _merge_entities(extracted, _extract_heuristic_entities(text))
    except Exception as exc:
        logger.warning("GLiNER extraction failed: %s", exc)
        return _extract_heuristic_entities(text)
    finally:
        if should_close:
            await client.aclose()


def _merge_entities(
    primary: Sequence[EntityCandidate],
    secondary: Sequence[EntityCandidate],
) -> list[EntityCandidate]:
    merged: list[EntityCandidate] = list(primary)
    seen = {
        (candidate.start_char, candidate.end_char, candidate.entity_type)
        for candidate in primary
    }
    for candidate in secondary:
        key = (candidate.start_char, candidate.end_char, candidate.entity_type)
        if key in seen:
            continue
        seen.add(key)
        merged.append(candidate)
    return sorted(merged, key=lambda candidate: (candidate.start_char, candidate.end_char))


def _is_in_code_block(text: str, pos: int) -> bool:
    return text[:pos].count("```") % 2 == 1
