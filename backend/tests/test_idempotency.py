from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from datum.services.idempotency import check_idempotency, cleanup_expired, store_idempotency


@pytest.mark.asyncio
async def test_check_idempotency_returns_cached_body_for_matching_scope():
    session = AsyncMock()
    record = SimpleNamespace(
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        scope="append_session_note",
        status_code=200,
        response_body={"ok": True},
    )
    session.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: record)

    result = await check_idempotency(session, "idem-1", scope="append_session_note")
    assert result == {"status_code": 200, "body": {"ok": True}}


@pytest.mark.asyncio
async def test_check_idempotency_ignores_expired_or_wrong_scope_records():
    session = AsyncMock()
    expired = SimpleNamespace(
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
        scope="append_session_note",
        status_code=200,
        response_body={},
    )
    session.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: expired)
    assert await check_idempotency(session, "idem-1") is None

    valid = SimpleNamespace(
        expires_at=datetime.now(UTC) + timedelta(minutes=1),
        scope="create_document",
        status_code=201,
        response_body={},
    )
    session.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: valid)
    assert await check_idempotency(session, "idem-2", scope="append_session_note") is None


@pytest.mark.asyncio
async def test_store_and_cleanup_idempotency_records():
    session = AsyncMock()
    session.add = MagicMock()
    await store_idempotency(session, "idem-3", "append_session_note", 200, {"ok": True})
    session.add.assert_called_once()
    session.flush.assert_awaited_once()

    session.execute.return_value = SimpleNamespace(fetchall=lambda: [1, 2, 3])
    deleted = await cleanup_expired(session)
    assert deleted == 3
