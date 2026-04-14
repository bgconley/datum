"""Prompt-injection boundary metadata for agent-facing content."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from datum.config import settings
from datum.services.content_scanning import redact_content, scan_for_pii, scan_for_secrets


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


def _project_pii_redaction_enabled(project_slug: str | None) -> bool:
    if not project_slug:
        return False

    project_yaml = Path(settings.projects_root) / project_slug / "project.yaml"
    if not project_yaml.exists():
        return False

    try:
        payload = yaml.safe_load(project_yaml.read_text()) or {}
    except Exception:
        return False
    if not isinstance(payload, dict):
        return False
    return bool(payload.get("pii_redact_in_api", False))


def sanitize_agent_content(content: str, *, project_slug: str | None = None) -> str:
    matches = scan_for_secrets(content)
    if _project_pii_redaction_enabled(project_slug):
        matches.extend(scan_for_pii(content))
    return redact_content(content, matches)


def wrap_content(
    content: str,
    kind: ContentKind,
    *,
    project_slug: str | None = None,
) -> dict[str, Any]:
    trust = _TRUST_LEVELS[kind]
    sanitized = sanitize_agent_content(content, project_slug=project_slug)
    return {
        "content": sanitized,
        "content_kind": kind.value,
        "trusted_for": trust["trusted_for"],
        "not_trusted_for": trust["not_trusted_for"],
    }
