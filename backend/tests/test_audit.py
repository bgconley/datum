from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from datum.services.audit import AuditFilter, log_agent_audit, query_audit_events


@pytest.mark.asyncio
async def test_log_agent_audit_flushes_event():
    session = SimpleNamespace(add=None, flush=None)
    added: list[object] = []

    def add(obj):
        added.append(obj)

    async def flush():
        return None

    session.add = add
    session.flush = flush

    event = await log_agent_audit(
        session,
        actor_type="agent",
        actor_name="codex",
        operation="append_session_notes",
        request_id="req-1",
        metadata={"session_id": "sess-1"},
    )

    assert added[0] is event
    assert event.actor_type == "agent"
    assert event.metadata_ == {"session_id": "sess-1"}


@pytest.mark.asyncio
async def test_query_audit_events_builds_expected_filter():
    captured = {}

    class FakeSession:
        async def execute(self, statement):
            captured["statement"] = str(statement)
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))

    events = await query_audit_events(
        FakeSession(),
        AuditFilter(
            project_id=uuid4(),
            actor_type="agent",
            actor_name="codex",
            operation="append_session_notes",
            since=datetime.now(UTC) - timedelta(days=1),
            until=datetime.now(UTC),
            limit=10,
            offset=5,
        ),
    )
    assert events == []
    rendered = captured["statement"]
    assert "audit_events" in rendered
    assert "actor_type" in rendered
    assert "operation" in rendered
