from pathlib import Path
from uuid import uuid4

import pytest

from datum.models.core import Project
from datum.models.intelligence import Decision, OpenQuestion
from datum.schemas.inbox import AcceptCandidateRequest
from datum.services.intelligence import accept_candidate, reject_candidate


class _FakeSession:
    def __init__(self, objects):
        self._objects = objects
        self.commit_calls = 0

    async def get(self, model, key):
        return self._objects.get((model, key))

    async def commit(self):
        self.commit_calls += 1


@pytest.mark.asyncio
async def test_accept_candidate_writes_curated_decision_record(monkeypatch, tmp_path: Path):
    project_path = tmp_path / "intel"
    project = Project(
        id=uuid4(),
        uid="proj_intel",
        slug="intel",
        name="Intel",
        filesystem_path=str(project_path),
        project_yaml_hash="sha256:project",
    )
    decision = Decision(
        id=uuid4(),
        uid="dec_test",
        project_id=project.id,
        title="Use ParadeDB",
        status="accepted",
        context="Need hybrid search.",
        decision="Use ParadeDB for BM25 plus pgvector.",
        consequences="Single database.",
        curation_status="candidate",
        extraction_method="structured_adr",
        confidence=1.0,
    )
    session = _FakeSession({(Decision, decision.id): decision})
    audit_events: list[dict[str, str | None]] = []

    async def fake_get_project_or_404(session, slug):
        del session
        assert slug == "intel"
        return project

    async def fake_log_audit_event(session, **kwargs):
        del session
        audit_events.append(kwargs)

    monkeypatch.setattr("datum.services.intelligence.get_project_or_404", fake_get_project_or_404)
    monkeypatch.setattr("datum.services.intelligence.log_audit_event", fake_log_audit_event)

    result = await accept_candidate(
        session,
        slug="intel",
        candidate_type="decision",
        candidate_id=str(decision.id),
        body=AcceptCandidateRequest(
            title="Use ParadeDB for hybrid retrieval",
            decision="Use ParadeDB for BM25, pgvector, and operational simplicity.",
            consequences="Search storage stays in one database.",
        ),
    )

    record_path = project_path / ".piq" / "records" / "decisions" / "dec_test.yaml"
    assert record_path.exists()
    record_text = record_path.read_text()
    assert "Use ParadeDB for hybrid retrieval" in record_text
    assert "Search storage stays in one database." in record_text
    assert result.curation_status == "edited"
    assert result.canonical_record_path == ".piq/records/decisions/dec_test.yaml"
    assert session.commit_calls == 1
    assert audit_events[0]["operation"] == "accept_candidate"


@pytest.mark.asyncio
async def test_reject_candidate_marks_status(monkeypatch, tmp_path: Path):
    project = Project(
        id=uuid4(),
        uid="proj_questions",
        slug="questions",
        name="Questions",
        filesystem_path=str(tmp_path / "questions"),
        project_yaml_hash="sha256:project",
    )
    question = OpenQuestion(
        id=uuid4(),
        project_id=project.id,
        question="What is the rollback plan?",
        context="Release readiness.",
        curation_status="candidate",
    )
    session = _FakeSession({(OpenQuestion, question.id): question})

    async def fake_get_project_or_404(session, slug):
        del session
        assert slug == "questions"
        return project

    async def fake_log_audit_event(session, **kwargs):
        del session, kwargs
        return None

    monkeypatch.setattr("datum.services.intelligence.get_project_or_404", fake_get_project_or_404)
    monkeypatch.setattr("datum.services.intelligence.log_audit_event", fake_log_audit_event)

    result = await reject_candidate(
        session,
        slug="questions",
        candidate_type="open_question",
        candidate_id=str(question.id),
    )

    assert question.curation_status == "rejected"
    assert result.curation_status == "rejected"
    assert session.commit_calls == 1

