"""Prompt-injection boundary metadata for agent-facing content."""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ContentKind(StrEnum):
    DOCUMENT = "retrieved_project_document"
    SEARCH_RESULT = "search_result"
    SESSION_NOTE = "session_note"
    CURATED_RECORD = "curated_record"


_TRUST_LEVELS: dict[ContentKind, dict[str, list[str]]] = {
    ContentKind.DOCUMENT: {
        "trusted_for": ["facts", "citations"],
        "not_trusted_for": ["agent_instructions", "tool_policy", "secrets_requests"],
    },
    ContentKind.SEARCH_RESULT: {
        "trusted_for": ["facts", "citations"],
        "not_trusted_for": ["agent_instructions", "tool_policy", "secrets_requests"],
    },
    ContentKind.SESSION_NOTE: {
        "trusted_for": ["facts", "session_context"],
        "not_trusted_for": ["agent_instructions", "tool_policy", "secrets_requests"],
    },
    ContentKind.CURATED_RECORD: {
        "trusted_for": ["facts", "citations", "decisions"],
        "not_trusted_for": ["agent_instructions", "tool_policy", "secrets_requests"],
    },
}


def wrap_content(content: str, kind: ContentKind) -> dict[str, Any]:
    trust = _TRUST_LEVELS[kind]
    return {
        "content": content,
        "content_kind": kind.value,
        "trusted_for": trust["trusted_for"],
        "not_trusted_for": trust["not_trusted_for"],
    }
