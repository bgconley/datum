from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from datum.models.core import Project
from datum.models.lifecycle import SessionDelta
from datum.services.session_state import get_session_by_session_id, mark_clean, mark_dirty
from datum.services.sessions import (
    SessionMetadata,
    _render_session_document,
    create_session_note,
    find_session_note,
    parse_session_frontmatter,
)
from datum.services.versioning import create_version


@dataclass(slots=True)
class FlushSummary:
    counts: dict[str, int]
    recent_paths: list[str] = field(default_factory=list)
    recent_commands: list[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        lines = ["## Lifecycle Flush", ""]
        if self.counts:
            lines.append("### Delta Counts")
            for key in sorted(self.counts):
                lines.append(f"- {key}: {self.counts[key]}")
            lines.append("")
        if self.recent_paths:
            lines.append("### Paths")
            for path in self.recent_paths:
                lines.append(f"- {path}")
            lines.append("")
        if self.recent_commands:
            lines.append("### Commands")
            for command in self.recent_commands:
                lines.append(f"- `{command}`")
            lines.append("")
        lines.append(f"_Flushed at {datetime.now(UTC).isoformat()}_")
        return "\n".join(lines)


@dataclass(slots=True)
class FlushResult:
    flushed_count: int
    summary: FlushSummary | None = None
    session_note_path: str | None = None


async def record_delta(
    session_id: str,
    delta_type: str,
    detail: dict,
    db: AsyncSession,
    *,
    summary_text: str | None = None,
) -> SessionDelta:
    row = await get_session_by_session_id(session_id, db)
    if row is None:
        raise ValueError(f"Session '{session_id}' not found")
    delta = SessionDelta(
        agent_session_id=row.id,
        delta_type=delta_type,
        detail=detail,
        summary_text=summary_text,
        flushed=False,
    )
    db.add(delta)
    await db.flush()
    await mark_dirty(session_id, delta_type, db)
    return delta


async def get_unflushed_deltas(
    session_id: str,
    db: AsyncSession,
) -> list[SessionDelta]:
    row = await get_session_by_session_id(session_id, db)
    if row is None:
        return []
    result = await db.execute(
        select(SessionDelta)
        .where(
            SessionDelta.agent_session_id == row.id,
            SessionDelta.flushed.is_(False),
        )
        .order_by(SessionDelta.created_at.asc())
    )
    return list(result.scalars().all())


def build_flush_summary(deltas: list[SessionDelta]) -> FlushSummary:
    counts: dict[str, int] = {}
    seen_paths: list[str] = []
    seen_commands: list[str] = []
    for delta in deltas:
        counts[delta.delta_type] = counts.get(delta.delta_type, 0) + 1
        path = delta.detail.get("path")
        if isinstance(path, str) and path not in seen_paths:
            seen_paths.append(path)
        command = delta.detail.get("command")
        if isinstance(command, str) and command not in seen_commands:
            seen_commands.append(command)
    return FlushSummary(
        counts=counts,
        recent_paths=seen_paths[:10],
        recent_commands=seen_commands[:10],
    )


def _append_flush_to_session_note(project_dir: Path, session_id: str, summary_markdown: str) -> str:
    note_path = find_session_note(project_dir, session_id)
    if note_path is None:
        note_path = create_session_note(
            project_dir,
            SessionMetadata(
                session_id=session_id,
                agent_name="datum-lifecycle",
                summary="Lifecycle delta flush",
                content=summary_markdown,
            ),
        )
        return note_path.relative_to(project_dir).as_posix()

    existing_text = note_path.read_text()
    meta = parse_session_frontmatter(existing_text)
    body = meta.content.strip()
    if body:
        body += "\n\n---\n\n"
    body += summary_markdown.strip()
    payload = SessionMetadata(
        session_id=meta.session_id,
        agent_name=meta.agent_name or "datum-lifecycle",
        summary=meta.summary or "Lifecycle delta flush",
        content=body,
        repo_path=meta.repo_path,
        git_branch=meta.git_branch,
        git_commit=meta.git_commit,
        started_at=meta.started_at,
        ended_at=meta.ended_at,
        files_touched=meta.files_touched,
        commands_run=meta.commands_run,
        next_steps=meta.next_steps,
    )
    relative_path = note_path.relative_to(project_dir).as_posix()
    version = create_version(
        project_path=project_dir,
        canonical_path=relative_path,
        content=_render_session_document(payload, body),
        change_source="agent",
    )
    if version is None:
        raise RuntimeError(f"Failed to append lifecycle flush to {relative_path}")
    return relative_path


async def flush_deltas(
    session_id: str,
    db: AsyncSession,
    *,
    write_session_note: bool = True,
) -> FlushResult:
    deltas = await get_unflushed_deltas(session_id, db)
    if not deltas:
        await mark_clean(session_id, db)
        return FlushResult(flushed_count=0)

    summary = build_flush_summary(deltas)
    session_note_path: str | None = None
    if write_session_note:
        session_row = await get_session_by_session_id(session_id, db)
        project_row = None
        if session_row is not None and session_row.project_id is not None:
            project_row = await db.get(Project, session_row.project_id)
        if project_row is not None:
            session_note_path = _append_flush_to_session_note(
                Path(project_row.filesystem_path),
                session_id,
                summary.to_markdown(),
            )

    for delta in deltas:
        delta.flushed = True
    await mark_clean(session_id, db)
    await db.commit()
    return FlushResult(
        flushed_count=len(deltas),
        summary=summary,
        session_note_path=session_note_path,
    )
