"""Deterministic candidate extraction for decisions, requirements, and open questions."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(slots=True)
class DecisionCandidate:
    title: str
    status: str | None
    context: str | None
    decision: str | None
    consequences: str | None
    extraction_method: str
    confidence: float
    start_char: int
    end_char: int


@dataclass(slots=True)
class RequirementCandidate:
    requirement_id: str | None
    title: str
    description: str | None
    priority: str | None
    extraction_method: str
    confidence: float
    start_char: int
    end_char: int


@dataclass(slots=True)
class OpenQuestionCandidate:
    question: str
    context: str | None
    extraction_method: str
    confidence: float
    start_char: int
    end_char: int


ADR_TITLE_RE = re.compile(r"^#\s+(?:ADR[-\s]?\d+[:\s]*)?(.+)$", re.MULTILINE)
ADR_SECTION_RE = re.compile(
    r"^##\s+(Status|Context|Decision|Consequences)\s*$",
    re.MULTILINE | re.IGNORECASE,
)
REQ_ID_RE = re.compile(r"^(REQ-\d+|US-\d+)[:\s]+(.+)$", re.MULTILINE)
SHALL_MUST_RE = re.compile(
    r"^(.{0,20}(?:shall|must|should|will)\s+.{10,200})$",
    re.MULTILINE | re.IGNORECASE,
)
QUESTION_RE = re.compile(r"^([^#`\n].{10,300}\?)\s*$", re.MULTILINE)
TODO_RE = re.compile(
    r"^(?:TODO|TBD|OPEN QUESTION|QUESTION)[:\s]+(.{5,300})$",
    re.MULTILINE | re.IGNORECASE,
)
HEADING_RE = re.compile(r"^#{1,6}\s+")
QUESTION_PREFIX_RE = re.compile(r"^(?:open\s+question|question)[:\s]+", re.IGNORECASE)


def extract_decisions_from_adr(text: str) -> list[DecisionCandidate]:
    sections = _parse_adr_sections(text)
    if "decision" not in sections:
        return []

    title_match = ADR_TITLE_RE.search(text)
    title = title_match.group(1).strip() if title_match else "Untitled Decision"
    if title.casefold().startswith("adr:"):
        title = title.split(":", 1)[1].strip() or "Untitled Decision"
    return [
        DecisionCandidate(
            title=title,
            status=_normalize_decision_status(sections.get("status")),
            context=sections.get("context"),
            decision=sections.get("decision"),
            consequences=sections.get("consequences"),
            extraction_method="structured_adr",
            confidence=1.0,
            start_char=0,
            end_char=len(text),
        )
    ]


def extract_requirements(text: str) -> list[RequirementCandidate]:
    candidates: list[RequirementCandidate] = []
    seen_titles: set[str] = set()
    explicit_line_starts: set[int] = set()

    for match in REQ_ID_RE.finditer(text):
        title = match.group(2).strip()
        if title in seen_titles:
            continue
        seen_titles.add(title)
        explicit_line_starts.add(match.start())
        candidates.append(
            RequirementCandidate(
                requirement_id=match.group(1),
                title=title,
                description=None,
                priority=_detect_priority(title),
                extraction_method="regex_req_id",
                confidence=1.0,
                start_char=match.start(),
                end_char=match.end(),
            )
        )

    for match in SHALL_MUST_RE.finditer(text):
        line = match.group(1).strip()
        if (
            line in seen_titles
            or match.start() in explicit_line_starts
            or _is_in_code_block(text, match.start())
            or _looks_like_question_candidate(line)
        ):
            continue
        seen_titles.add(line)
        candidates.append(
            RequirementCandidate(
                requirement_id=None,
                title=line,
                description=None,
                priority=_detect_priority(line),
                extraction_method="regex_shall_must",
                confidence=0.8,
                start_char=match.start(),
                end_char=match.end(),
            )
        )

    return candidates


def extract_open_questions(text: str) -> list[OpenQuestionCandidate]:
    candidates: list[OpenQuestionCandidate] = []
    seen_questions: set[str] = set()

    for match in QUESTION_RE.finditer(text):
        question = _normalize_question_text(match.group(1).strip())
        if question in seen_questions:
            continue

        line_start = text.rfind("\n", 0, match.start()) + 1
        line = text[line_start:match.end()]
        if HEADING_RE.match(line) or _is_in_code_block(text, match.start()):
            continue

        seen_questions.add(question)
        context_line_end = max(0, line_start - 1)
        context_line_start = text.rfind("\n", 0, context_line_end)
        context = text[context_line_start + 1:line_start].strip() or None
        candidates.append(
            OpenQuestionCandidate(
                question=question,
                context=context,
                extraction_method="regex_question_mark",
                confidence=0.7,
                start_char=match.start(),
                end_char=match.end(),
            )
        )

    for match in TODO_RE.finditer(text):
        question = _normalize_question_text(match.group(1).strip())
        if question in seen_questions or _is_in_code_block(text, match.start()):
            continue
        seen_questions.add(question)
        candidates.append(
            OpenQuestionCandidate(
                question=question,
                context=None,
                extraction_method="regex_todo_marker",
                confidence=0.9,
                start_char=match.start(),
                end_char=match.end(),
            )
        )

    return candidates


def _parse_adr_sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    matches = list(ADR_SECTION_RE.finditer(text))
    for index, match in enumerate(matches):
        section_name = match.group(1).strip().lower()
        start_char = match.end()
        end_char = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        content = text[start_char:end_char].strip()
        if content:
            sections[section_name] = content
    return sections


def _normalize_decision_status(value: str | None) -> str | None:
    if not value:
        return None
    first_line = value.strip().splitlines()[0].casefold()
    mapping = {
        "proposed": "proposed",
        "accepted": "accepted",
        "superseded": "superseded",
        "deprecated": "deprecated",
    }
    return mapping.get(first_line, first_line)


def _detect_priority(text: str) -> str | None:
    lowered = text.casefold()
    if "must" in lowered or "shall" in lowered:
        return "must"
    if "should" in lowered:
        return "should"
    if "could" in lowered or "may" in lowered:
        return "could"
    return None


def _is_in_code_block(text: str, pos: int) -> bool:
    return text[:pos].count("```") % 2 == 1


def _normalize_question_text(text: str) -> str:
    return QUESTION_PREFIX_RE.sub("", text).strip()


def _looks_like_question_candidate(text: str) -> bool:
    lowered = text.casefold().strip()
    return (
        lowered.endswith("?")
        or lowered.startswith("open question:")
        or lowered.startswith("question:")
        or lowered.startswith("todo:")
        or lowered.startswith("tbd:")
    )
