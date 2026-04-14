from types import SimpleNamespace

import pytest

from datum.services.stop_barrier import evaluate_stop_barrier
from datum.services.write_barrier import WriteBarrierConfig, evaluate_write_barrier


@pytest.mark.asyncio
async def test_write_barrier_blocks_without_session_in_blocking_mode():
    result = await evaluate_write_barrier(
        session_id=None,
        db=object(),  # Unused on missing-session path.
        config=WriteBarrierConfig(enforcement_mode="blocking", preflight_ttl=300),
    )

    assert result.blocked is True
    assert result.detail["error"] == "preflight_required"
    assert result.detail["reason"] == "missing_session"


@pytest.mark.asyncio
async def test_write_barrier_allows_missing_session_in_advisory_mode():
    result = await evaluate_write_barrier(
        session_id=None,
        db=object(),  # Unused on missing-session path.
        config=WriteBarrierConfig(enforcement_mode="advisory", preflight_ttl=300),
    )

    assert result.blocked is False
    assert result.advisory is not None


@pytest.mark.asyncio
async def test_write_barrier_blocks_missing_preflight(monkeypatch):
    async def fake_check_preflight(session_id, db, *, ttl_seconds):
        del session_id, db, ttl_seconds
        return SimpleNamespace(
            allowed=False,
            reason="no_preflight",
            needed_actions=["get_project_context", "search_project_memory"],
        )

    monkeypatch.setattr("datum.services.write_barrier.check_preflight", fake_check_preflight)

    result = await evaluate_write_barrier(
        session_id="ses_write_block",
        db=object(),
        config=WriteBarrierConfig(enforcement_mode="blocking", preflight_ttl=300),
    )

    assert result.blocked is True
    assert result.detail["reason"] == "no_preflight"


@pytest.mark.asyncio
async def test_write_barrier_allows_recent_preflight(monkeypatch):
    async def fake_check_preflight(session_id, db, *, ttl_seconds):
        del session_id, db, ttl_seconds
        return SimpleNamespace(allowed=True, reason="", needed_actions=[])

    monkeypatch.setattr("datum.services.write_barrier.check_preflight", fake_check_preflight)

    result = await evaluate_write_barrier(
        session_id="ses_write_ok",
        db=object(),
        config=WriteBarrierConfig(enforcement_mode="blocking", preflight_ttl=300),
    )

    assert result.blocked is False
    assert result.detail == {}


@pytest.mark.asyncio
async def test_stop_barrier_blocks_dirty_session(monkeypatch):
    async def fake_get_session(session_id, db):
        del session_id, db
        return SimpleNamespace(is_dirty=True, dirty_reasons={"doc_update": 1})

    async def fake_get_unflushed(session_id, db):
        del session_id, db
        return [SimpleNamespace(delta_type="doc_update", detail={"path": "docs/a.md"})]

    monkeypatch.setattr(
        "datum.services.stop_barrier.get_session_by_session_id",
        fake_get_session,
    )
    monkeypatch.setattr(
        "datum.services.stop_barrier.get_unflushed_deltas",
        fake_get_unflushed,
    )

    result = await evaluate_stop_barrier(
        "ses_stop_block",
        object(),
        enforcement_mode="blocking",
    )

    assert result.blocked is True
    assert result.detail["error"] == "dirty_session"
    assert result.detail["unflushed_delta_count"] == 1


@pytest.mark.asyncio
async def test_stop_barrier_allows_clean_session(monkeypatch):
    async def fake_get_session(session_id, db):
        del session_id, db
        return SimpleNamespace(is_dirty=False, dirty_reasons={})

    async def fake_get_unflushed(session_id, db):
        del session_id, db
        return []

    monkeypatch.setattr(
        "datum.services.stop_barrier.get_session_by_session_id",
        fake_get_session,
    )
    monkeypatch.setattr(
        "datum.services.stop_barrier.get_unflushed_deltas",
        fake_get_unflushed,
    )

    result = await evaluate_stop_barrier(
        "ses_stop_ok",
        object(),
        enforcement_mode="blocking",
    )

    assert result.blocked is False
    assert result.detail == {}
