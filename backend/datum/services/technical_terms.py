"""Regex-based technical term extraction for exact-match search."""

from __future__ import annotations

from dataclasses import dataclass
import re

TECHNICAL_TERMS_PIPELINE_NAME = "regex-technical-terms"
TECHNICAL_TERMS_PIPELINE_VERSION = "regex-v1"

@dataclass(slots=True)
class TermMatch:
    normalized_text: str
    raw_text: str
    term_type: str
    start_char: int
    end_char: int
    confidence: float = 1.0


PATTERNS: list[tuple[str, re.Pattern[str], float]] = [
    (
        "api_route",
        re.compile(r"(?:GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+(/[\w./{}\-:]+)"),
        1.0,
    ),
    (
        "file_path",
        re.compile(r"(?<!\w)(\.\.?/[\w./-]+|/[\w./-]+(?:\.[\w.-]+)?)"),
        0.9,
    ),
    ("env_var", re.compile(r"\b([A-Z][A-Z0-9_]{2,})\b"), 0.8),
    ("version", re.compile(r"\bv?\d+\.\d+(?:\.\d+)?(?:-[\w.]+)?\b"), 0.9),
    (
        "sql_identifier",
        re.compile(r"(?:FROM|TABLE|JOIN|INTO|UPDATE|INDEX\s+ON)\s+([A-Za-z_][\w$]*)", re.IGNORECASE),
        0.9,
    ),
    (
        "package",
        re.compile(r"(?:pip\s+install|npm\s+install|yarn\s+add)\s+([\w\[\].-]+(?:\s+[\w\[\].-]+)*)", re.IGNORECASE),
        0.8,
    ),
    ("port", re.compile(r"(?::(\d{2,5})(?!\d))|(?:port\s+(\d{2,5}))", re.IGNORECASE), 0.7),
]

ENV_STOPWORDS = {
    "AND",
    "API",
    "CSS",
    "DELETE",
    "FROM",
    "GET",
    "HEAD",
    "HTML",
    "HTTP",
    "HTTPS",
    "INTO",
    "JOIN",
    "JSON",
    "NOT",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
    "SELECT",
    "SQL",
    "TABLE",
    "THE",
    "URL",
    "WHERE",
    "YAML",
}


def extract_technical_terms(text: str) -> list[TermMatch]:
    if not text:
        return []

    matches: list[TermMatch] = []
    seen_spans: set[tuple[int, int]] = set()

    for term_type, pattern, confidence in PATTERNS:
        for match in pattern.finditer(text):
            groups = [group for group in match.groups() if group is not None]

            if term_type == "package" and groups:
                package_group = groups[0]
                group_start = match.start() + match.group().index(package_group)
                cursor = group_start
                for package in package_group.split():
                    start = text.find(package, cursor)
                    if start < 0:
                        continue
                    end = start + len(package)
                    cursor = end
                    if (start, end) in seen_spans:
                        continue
                    seen_spans.add((start, end))
                    matches.append(
                        TermMatch(
                            normalized_text=package.lower().split("[", 1)[0],
                            raw_text=package,
                            term_type=term_type,
                            start_char=start,
                            end_char=end,
                            confidence=confidence,
                        )
                    )
                continue

            if groups:
                raw = groups[0]
                start = match.start() + match.group().index(raw)
                end = start + len(raw)
            else:
                raw = match.group()
                start = match.start()
                end = match.end()

            if (start, end) in seen_spans:
                continue
            if term_type == "env_var" and raw in ENV_STOPWORDS:
                continue

            seen_spans.add((start, end))
            matches.append(
                TermMatch(
                    normalized_text=_normalize_term(term_type, raw),
                    raw_text=raw,
                    term_type=term_type,
                    start_char=start,
                    end_char=end,
                    confidence=confidence,
                )
            )

    return sorted(matches, key=lambda item: (item.start_char, item.end_char))


def _normalize_term(term_type: str, raw_text: str) -> str:
    if term_type in {"package", "sql_identifier"}:
        return raw_text.lower()
    return raw_text
