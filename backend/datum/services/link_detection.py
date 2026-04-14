"""Document link detection for cabinet content."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(slots=True)
class LinkCandidate:
    target_path: str
    link_type: str
    anchor_text: str
    confidence: float
    start_char: int
    end_char: int


_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_PATH_REF_RE = re.compile(
    r"(?<![`(])(?P<path>(?:\.{1,2}/)?(?:[\w.-]+/)*[\w.-]+\.[A-Za-z0-9]{1,10})(?=$|[\s),.;:])"
)


def _normalize_path(raw_path: str) -> str | None:
    path = raw_path.strip()
    if not path or path.startswith(("http://", "https://", "mailto:", "#")):
        return None
    path = path.split("#", 1)[0].strip()
    if not path:
        return None
    normalized = str(PurePosixPath(path))
    if normalized == ".":
        return None
    return normalized


def detect_markdown_links(content: str) -> list[LinkCandidate]:
    candidates: list[LinkCandidate] = []
    for match in _MARKDOWN_LINK_RE.finditer(content):
        normalized = _normalize_path(match.group(2))
        if normalized is None:
            continue
        candidates.append(
            LinkCandidate(
                target_path=normalized,
                link_type="references",
                anchor_text=match.group(1).strip(),
                confidence=1.0,
                start_char=match.start(),
                end_char=match.end(),
            )
        )
    return candidates


def detect_path_references(content: str, known_paths: set[str]) -> list[LinkCandidate]:
    candidates: list[LinkCandidate] = []
    normalized_known = {str(PurePosixPath(path)) for path in known_paths}
    for match in _PATH_REF_RE.finditer(content):
        normalized = _normalize_path(match.group("path"))
        if normalized is None or normalized not in normalized_known:
            continue
        candidates.append(
            LinkCandidate(
                target_path=normalized,
                link_type="references",
                anchor_text=match.group("path"),
                confidence=0.8,
                start_char=match.start("path"),
                end_char=match.end("path"),
            )
        )
    return candidates


def detect_all_links(content: str, known_paths: set[str]) -> list[LinkCandidate]:
    candidates = detect_markdown_links(content)
    candidates.extend(detect_path_references(content, known_paths))

    seen: set[tuple[str, int, int]] = set()
    unique: list[LinkCandidate] = []
    for candidate in sorted(candidates, key=lambda item: (item.start_char, item.end_char)):
        key = (candidate.target_path, candidate.start_char, candidate.end_char)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique
