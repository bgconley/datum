"""Staleness and gap detection for project intelligence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from datum.models.core import Document, DocumentVersion, Project
from datum.services.link_detection import detect_all_links
from datum.services.versioning import read_version_content


@dataclass(slots=True)
class StalenessCandidate:
    insight_type: str
    severity: str
    title: str
    explanation: str
    confidence: float
    evidence: dict[str, Any] = field(default_factory=dict)


def detect_stale_documents(
    docs: list[dict[str, datetime]],
    *,
    max_age_days: int = 60,
) -> list[StalenessCandidate]:
    now = datetime.now(UTC)
    threshold = now - timedelta(days=max_age_days)
    candidates: list[StalenessCandidate] = []
    for doc in docs:
        updated_at = doc["updated_at"]
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=UTC)
        if updated_at >= threshold:
            continue
        age_days = (now - updated_at).days
        candidates.append(
            StalenessCandidate(
                insight_type="stale_document",
                severity="info" if age_days < 120 else "warning",
                title=f"Stale document: {doc['path']}",
                explanation=(
                    f"{doc['path']} has not been updated in {age_days} days."
                ),
                confidence=1.0,
                evidence={
                    "path": doc["path"],
                    "updated_at": updated_at.isoformat(),
                    "age_days": age_days,
                    "threshold_days": max_age_days,
                },
            )
        )
    return candidates


def detect_broken_links(
    links: list[dict[str, str]],
    existing_paths: set[str],
) -> list[StalenessCandidate]:
    candidates: list[StalenessCandidate] = []
    for link in links:
        if link["target_path"] in existing_paths:
            continue
        candidates.append(
            StalenessCandidate(
                insight_type="gap",
                severity="warning",
                title=f"Broken link: {link['source']} → {link['target_path']}",
                explanation=(
                    f"{link['source']} references {link['target_path']} but that "
                    "document does not exist."
                ),
                confidence=1.0,
                evidence=link,
            )
        )
    return candidates


async def detect_staleness_for_project(
    session: AsyncSession,
    project_id,
    *,
    max_age_days: int = 60,
) -> list[StalenessCandidate]:
    project = await session.get(Project, project_id)
    if project is None:
        return []

    result = await session.execute(
        select(
            Document.canonical_path,
            Document.current_version_id,
            Document.updated_at,
        ).where(Document.project_id == project_id)
    )
    rows = result.fetchall()
    docs = [{"path": row[0], "updated_at": row[2]} for row in rows if row[2] is not None]
    candidates = detect_stale_documents(docs, max_age_days=max_age_days)

    existing_paths = {row[0] for row in rows}
    broken_link_rows: list[dict[str, str]] = []
    project_path = Path(project.filesystem_path)
    for canonical_path, current_version_id, _updated_at in rows:
        if current_version_id is None:
            continue
        version = await session.get(DocumentVersion, current_version_id)
        if version is None:
            continue
        content_bytes = read_version_content(
            project_path,
            canonical_path,
            version.version_number,
            branch=version.branch,
        )
        if content_bytes is None:
            continue
        content = content_bytes.decode("utf-8", errors="replace")
        for candidate in detect_all_links(content, existing_paths):
            broken_link_rows.append(
                {
                    "source": canonical_path,
                    "target_path": candidate.target_path,
                    "anchor": candidate.anchor_text,
                }
            )

    candidates.extend(detect_broken_links(broken_link_rows, existing_paths))
    return candidates
