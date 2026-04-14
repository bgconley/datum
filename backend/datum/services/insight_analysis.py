"""Project insight analysis orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from datum.models.intelligence import Insight
from datum.services.contradiction import detect_contradictions_for_project
from datum.services.staleness import detect_staleness_for_project


@dataclass(slots=True)
class AnalysisResult:
    contradictions_found: int
    staleness_found: int
    insights_created: int
    insights_skipped: int


class InsightCandidate(Protocol):
    insight_type: str
    severity: str
    title: str
    explanation: str
    confidence: float
    evidence: dict


def should_create_insight(title: str, existing_statuses: dict[str, str]) -> bool:
    return title not in existing_statuses


async def run_insight_analysis(
    session: AsyncSession,
    project_id,
    max_age_days: int = 60,
) -> AnalysisResult:
    result = await session.execute(
        select(Insight.title, Insight.status).where(Insight.project_id == project_id)
    )
    existing_statuses = {title: status for title, status in result.fetchall()}

    contradictions = await detect_contradictions_for_project(session, project_id)
    staleness = await detect_staleness_for_project(session, project_id, max_age_days=max_age_days)
    candidates: list[InsightCandidate] = [*contradictions, *staleness]

    created = 0
    skipped = 0
    for candidate in candidates:
        if not should_create_insight(candidate.title, existing_statuses):
            skipped += 1
            continue
        session.add(
            Insight(
                project_id=project_id,
                insight_type=candidate.insight_type,
                severity=candidate.severity,
                confidence=candidate.confidence,
                status="open",
                title=candidate.title,
                explanation=candidate.explanation,
                evidence=candidate.evidence,
            )
        )
        existing_statuses[candidate.title] = "open"
        created += 1
    await session.flush()

    return AnalysisResult(
        contradictions_found=len(contradictions),
        staleness_found=len(staleness),
        insights_created=created,
        insights_skipped=skipped,
    )
