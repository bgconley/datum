"""Session note creation, append, and listing for agent interactions."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import yaml

from datum.services.link_detection import LinkCandidate, detect_all_links
from datum.services.versioning import create_version


@dataclass(slots=True)
class SessionMetadata:
    session_id: str
    agent_name: str
    summary: str
    content: str = ""
    repo_path: str | None = None
    git_branch: str | None = None
    git_commit: str | None = None
    started_at: str | None = None
    ended_at: str | None = None
    files_touched: list[str] = field(default_factory=list)
    commands_run: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)


def build_session_filename(agent_name: str, summary: str) -> str:
    date_str = datetime.now(UTC).strftime("%Y-%m-%d")
    slug = re.sub(r"[^a-z0-9]+", "-", summary.lower().strip()).strip("-")[:60] or "session"
    return f"docs/sessions/{date_str}-{agent_name}-{slug}.md"


def _build_frontmatter(meta: SessionMetadata) -> str:
    payload: dict[str, object] = {
        "session_id": meta.session_id,
        "agent_name": meta.agent_name,
        "summary": meta.summary,
        "title": meta.summary,
        "type": "session",
        "status": "active",
        "started_at": meta.started_at or datetime.now(UTC).isoformat(),
        "files_touched": meta.files_touched,
        "commands_run": meta.commands_run,
        "next_steps": meta.next_steps,
    }
    if meta.ended_at:
        payload["ended_at"] = meta.ended_at
    if meta.repo_path:
        payload["repo_path"] = meta.repo_path
    if meta.git_branch:
        payload["git_branch"] = meta.git_branch
    if meta.git_commit:
        payload["git_commit"] = meta.git_commit
    return yaml.safe_dump(payload, default_flow_style=False, sort_keys=False).strip()


def _render_session_document(meta: SessionMetadata, body: str) -> bytes:
    frontmatter = _build_frontmatter(meta)
    return f"---\n{frontmatter}\n---\n\n{body.strip()}\n".encode()


def parse_session_frontmatter(content: str) -> SessionMetadata:
    if not content.startswith("---"):
        return SessionMetadata(session_id="", agent_name="", summary="")
    parts = content.split("---", 2)
    if len(parts) < 3:
        return SessionMetadata(session_id="", agent_name="", summary="")
    frontmatter = yaml.safe_load(parts[1]) or {}
    body = parts[2].strip()
    return SessionMetadata(
        session_id=str(frontmatter.get("session_id", "")),
        agent_name=str(frontmatter.get("agent_name", "")),
        summary=str(frontmatter.get("summary", "")),
        content=body,
        repo_path=frontmatter.get("repo_path"),
        git_branch=frontmatter.get("git_branch"),
        git_commit=frontmatter.get("git_commit"),
        started_at=frontmatter.get("started_at"),
        ended_at=frontmatter.get("ended_at"),
        files_touched=list(frontmatter.get("files_touched", [])),
        commands_run=list(frontmatter.get("commands_run", [])),
        next_steps=list(frontmatter.get("next_steps", [])),
    )


def create_session_note(project_dir: Path, meta: SessionMetadata) -> Path:
    relative_path = build_session_filename(meta.agent_name, meta.summary)
    absolute_path = project_dir / relative_path
    if absolute_path.exists():
        stemmed = absolute_path.with_name(
            f"{absolute_path.stem}-{meta.session_id[:12]}{absolute_path.suffix}"
        )
        relative_path = str(stemmed.relative_to(project_dir))
        absolute_path = stemmed

    version = create_version(
        project_path=project_dir,
        canonical_path=relative_path,
        content=_render_session_document(meta, meta.content or ""),
        change_source="agent",
    )
    if version is None:
        raise RuntimeError(f"Failed to create session note at {relative_path}")
    return absolute_path


def append_session_note(
    project_dir: Path,
    session_file: Path,
    new_content: str,
    new_files: list[str] | None = None,
    new_commands: list[str] | None = None,
    new_next_steps: list[str] | None = None,
    updated_summary: str | None = None,
) -> Path:
    existing = session_file.read_text()
    meta = parse_session_frontmatter(existing)
    if new_files:
        meta.files_touched = list(dict.fromkeys(meta.files_touched + new_files))
    if new_commands:
        meta.commands_run = meta.commands_run + new_commands
    if new_next_steps is not None:
        meta.next_steps = new_next_steps
    if updated_summary:
        meta.summary = updated_summary
    meta.ended_at = datetime.now(UTC).isoformat()

    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    appended = meta.content
    if appended:
        appended += f"\n\n---\n*Appended at {timestamp}*\n\n"
    appended += new_content.strip()
    meta.content = appended
    relative_path = session_file.relative_to(project_dir).as_posix()
    version = create_version(
        project_path=project_dir,
        canonical_path=relative_path,
        content=_render_session_document(meta, appended),
        change_source="agent",
    )
    if version is None:
        raise RuntimeError(f"Failed to append session note at {relative_path}")
    return session_file


def list_session_notes(project_dir: Path) -> list[dict]:
    sessions_dir = project_dir / "docs" / "sessions"
    if not sessions_dir.exists():
        return []

    results: list[dict] = []
    for path in sorted(sessions_dir.glob("*.md"), reverse=True):
        try:
            meta = parse_session_frontmatter(path.read_text())
        except Exception:
            continue
        results.append(
            {
                "session_id": meta.session_id,
                "agent_name": meta.agent_name,
                "summary": meta.summary,
                "path": path.relative_to(project_dir).as_posix(),
                "started_at": meta.started_at,
                "ended_at": meta.ended_at,
            }
        )
    return results


def find_session_note(project_dir: Path, session_id: str) -> Path | None:
    sessions_dir = project_dir / "docs" / "sessions"
    if not sessions_dir.exists():
        return None
    for path in sorted(sessions_dir.glob("*.md")):
        try:
            if parse_session_frontmatter(path.read_text()).session_id == session_id:
                return path
        except Exception:
            continue
    return None


def detect_session_document_links(content: str, known_paths: set[str]) -> list[LinkCandidate]:
    """Detect cabinet document references inside session note content."""
    return detect_all_links(content, known_paths)
