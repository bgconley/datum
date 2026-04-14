"""Secrets and PII scanning helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(slots=True)
class ScanMatch:
    match_type: str
    category: str
    matched_text: str
    start_char: int
    end_char: int


_API_KEY_RE = re.compile(r"(?:sk|pk|gh[pousr]|api)[_-][A-Za-z0-9_-]{16,}", re.IGNORECASE)
_BEARER_TOKEN_RE = re.compile(
    r"Bearer\s+[A-Za-z0-9\-._~+/]+=*(?:\.[A-Za-z0-9\-._~+/]+=*){1,2}"
)
_PASSWORD_RE = re.compile(
    r"(?:password|passwd|secret|private[_-]?key)\s*[:=]\s*[\"']?([^\s\"']{8,})",
    re.IGNORECASE,
)
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}(?!\d)")
_SSN_RE = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")


def scan_for_secrets(text: str) -> list[ScanMatch]:
    matches: list[ScanMatch] = []
    for pattern, kind in (
        (_API_KEY_RE, "api_key"),
        (_BEARER_TOKEN_RE, "bearer_token"),
        (_PASSWORD_RE, "password"),
    ):
        for match in pattern.finditer(text):
            matches.append(
                ScanMatch(
                    match_type=kind,
                    category="secret",
                    matched_text=match.group(0),
                    start_char=match.start(),
                    end_char=match.end(),
                )
            )
    return matches


def scan_for_pii(text: str) -> list[ScanMatch]:
    matches: list[ScanMatch] = []
    for pattern, kind in (
        (_EMAIL_RE, "email"),
        (_PHONE_RE, "phone"),
        (_SSN_RE, "ssn"),
    ):
        for match in pattern.finditer(text):
            matches.append(
                ScanMatch(
                    match_type=kind,
                    category="pii",
                    matched_text=match.group(0),
                    start_char=match.start(),
                    end_char=match.end(),
                )
            )
    return matches


def scan_all(text: str) -> list[ScanMatch]:
    return sorted([*scan_for_secrets(text), *scan_for_pii(text)], key=lambda item: item.start_char)


def redact_content(text: str, matches: list[ScanMatch]) -> str:
    if not matches:
        return text

    result = text
    for match in sorted(matches, key=lambda item: item.start_char, reverse=True):
        result = (
            result[: match.start_char]
            + f"[REDACTED:{match.match_type}]"
            + result[match.end_char :]
        )
    return result
