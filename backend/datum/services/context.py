"""Project context budgeting service for token-aware agent responses."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path

import frontmatter
import tiktoken
import yaml

_ENCODER = tiktoken.get_encoding("cl100k_base")


class DetailLevel(StrEnum):
    BRIEF = "brief"
    STANDARD = "standard"
    FULL = "full"


@dataclass(slots=True)
class ContextConfig:
    detail: DetailLevel = DetailLevel.STANDARD
    max_tokens: int = 8000
    recency_days: int | None = None
    limit_per_section: int | None = None


def count_tokens(text: str) -> int:
    if not text:
        return 0
    return len(_ENCODER.encode(text))


def truncate_to_budget(text: str, max_tokens: int) -> str:
    tokens = _ENCODER.encode(text)
    if len(tokens) <= max_tokens:
        return text
    return _ENCODER.decode(tokens[:max_tokens])


def _extract_summary(text: str) -> str:
    try:
        body = frontmatter.loads(text).content.strip()
    except Exception:
        body = text.strip()
    for paragraph in body.split("\n\n"):
        candidate = paragraph.strip()
        if candidate and not candidate.startswith("#"):
            return candidate[:500]
    return ""


def _read_yaml_records(records_dir: Path, record_type: str) -> list[dict]:
    type_dir = records_dir / record_type
    if not type_dir.exists():
        return []
    items: list[dict] = []
    for path in sorted(type_dir.glob("*.yaml")):
        try:
            payload = yaml.safe_load(path.read_text()) or {}
        except Exception:
            continue
        if payload:
            items.append(payload)
    return items


def _fit_section(items: list[dict], budget_remaining: int) -> tuple[list[dict], int]:
    fitted: list[dict] = []
    for item in items:
        item_tokens = count_tokens(str(item))
        if item_tokens > budget_remaining:
            continue
        fitted.append(item)
        budget_remaining -= item_tokens
        if budget_remaining <= 0:
            break
    return fitted, budget_remaining


def build_project_context(project_dir: Path, config: ContextConfig) -> dict:
    budget_remaining = config.max_tokens
    project_info: dict = {}
    project_yaml = project_dir / "project.yaml"
    if project_yaml.exists():
        project_info = yaml.safe_load(project_yaml.read_text()) or {}
        budget_remaining -= count_tokens(str(project_info))

    docs_dir = project_dir / "docs"
    document_entries: list[dict] = []
    cutoff: datetime | None = None
    if config.recency_days is not None:
        cutoff = datetime.now(UTC) - timedelta(days=config.recency_days)

    if docs_dir.exists():
        doc_paths = sorted(
            docs_dir.rglob("*.md"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for path in doc_paths:
            if cutoff is not None:
                mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
                if mtime < cutoff:
                    continue
            if (
                config.limit_per_section is not None
                and len(document_entries) >= config.limit_per_section
            ):
                break
            raw = path.read_text()
            try:
                post = frontmatter.loads(raw)
            except Exception:
                continue
            entry = {
                "path": path.relative_to(project_dir).as_posix(),
                "title": post.get("title", path.stem),
                "doc_type": post.get("type") or post.get("doc_type", "unknown"),
            }
            if config.detail in {DetailLevel.STANDARD, DetailLevel.FULL}:
                entry["summary"] = _extract_summary(raw)
            if config.detail == DetailLevel.FULL:
                entry["content"] = post.content.strip()

            entry_tokens = count_tokens(str(entry))
            if entry_tokens > budget_remaining:
                if (
                    config.detail == DetailLevel.FULL
                    and "content" in entry
                    and budget_remaining > 100
                ):
                    entry["content"] = truncate_to_budget(
                        entry["content"],
                        max(budget_remaining - 50, 0),
                    )
                    entry_tokens = count_tokens(str(entry))
                if entry_tokens > budget_remaining:
                    continue

            document_entries.append(entry)
            budget_remaining -= entry_tokens
            if budget_remaining <= 0:
                break

    records_dir = project_dir / ".piq" / "records"
    decisions = _read_yaml_records(records_dir, "decisions")
    requirements = _read_yaml_records(records_dir, "requirements")
    open_questions = _read_yaml_records(records_dir, "open-questions")

    if config.limit_per_section is not None:
        decisions = decisions[: config.limit_per_section]
        requirements = requirements[: config.limit_per_section]
        open_questions = open_questions[: config.limit_per_section]

    decisions, budget_remaining = _fit_section(decisions, budget_remaining)
    requirements, budget_remaining = _fit_section(requirements, budget_remaining)
    open_questions, budget_remaining = _fit_section(open_questions, budget_remaining)

    return {
        "project": project_info,
        "documents": document_entries,
        "decisions": decisions,
        "requirements": requirements,
        "open_questions": open_questions,
    }
