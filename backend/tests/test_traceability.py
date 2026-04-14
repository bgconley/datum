from types import SimpleNamespace
from uuid import uuid4

import pytest

from datum.services.traceability import get_traceability_chains


class _FakeScalars:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _FakeResult:
    def __init__(self, *, scalar_items=None, rows=None):
        self._scalar_items = scalar_items or []
        self._rows = rows or []

    def scalars(self):
        return _FakeScalars(self._scalar_items)

    def all(self):
        return self._rows


class _QueuedSession:
    def __init__(self, results):
        self._results = list(results)

    async def execute(self, statement):
        del statement
        return self._results.pop(0)


@pytest.mark.asyncio
async def test_traceability_follows_decision_links_to_schema_documents(monkeypatch):
    project = SimpleNamespace(id=uuid4(), slug="intel")
    requirement_version_id = uuid4()
    decision_version_id = uuid4()
    schema_version_id = uuid4()

    async def fake_get_project_or_404(session, slug):
        del session
        assert slug == "intel"
        return project

    monkeypatch.setattr("datum.services.traceability.get_project_or_404", fake_get_project_or_404)

    session = _QueuedSession(
        [
            _FakeResult(
                scalar_items=[
                    SimpleNamespace(
                        uid="req_auth",
                        title="Persist session ownership",
                        status="accepted",
                        description="Track owners in schema.",
                        priority="must",
                        source_version_id=requirement_version_id,
                    )
                ]
            ),
            _FakeResult(
                rows=[
                    (
                        SimpleNamespace(
                            uid="dec_auth",
                            title="Use ParadeDB",
                            status="accepted",
                            decision="Adopt ParadeDB for search.",
                            source_version_id=decision_version_id,
                        ),
                        "docs/decisions/adr-0001.md",
                    )
                ]
            ),
            _FakeResult(rows=[(schema_version_id, None)]),
            _FakeResult(
                rows=[
                    ("sessions.user_id", "column", "users.id", "column"),
                    ("users", "table", "sessions", "table"),
                ]
            ),
        ]
    )

    chains = await get_traceability_chains(session, "intel")

    assert len(chains) == 1
    assert chains[0].requirement is not None
    assert chains[0].requirement.uid == "req_auth"
    assert [node.uid for node in chains[0].decisions] == ["dec_auth"]
    assert {node.name for node in chains[0].schema_entities} == {
        "sessions.user_id",
        "users.id",
        "users",
        "sessions",
    }
