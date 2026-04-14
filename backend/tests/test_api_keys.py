from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from datum.services.api_keys import (
    SCOPE_HIERARCHY,
    _hash_key,
    generate_api_key,
    has_scope,
    list_api_keys,
    revoke_api_key,
    validate_api_key,
)


def test_scope_hierarchy_orders_scopes():
    assert SCOPE_HIERARCHY["read"] < SCOPE_HIERARCHY["readwrite"] < SCOPE_HIERARCHY["admin"]


def test_hash_key_is_deterministic():
    assert _hash_key("datum_rw_test") == _hash_key("datum_rw_test")


def test_has_scope_handles_strings_and_models():
    assert has_scope("admin", "readwrite") is True
    assert has_scope(SimpleNamespace(scope="readwrite"), "read") is True
    assert has_scope(SimpleNamespace(scope="read"), "admin") is False


@pytest.mark.asyncio
async def test_generate_api_key_creates_expected_prefix():
    session = AsyncMock()
    session.add = MagicMock()
    created = await generate_api_key(session, "test", "readwrite", created_by="tester")
    assert created.key_plaintext.startswith("datum_rw_")
    assert created.scope == "readwrite"
    session.add.assert_called_once()
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_api_key_rejects_unknown_scope():
    session = AsyncMock()
    session.add = MagicMock()
    with pytest.raises(ValueError, match="Invalid scope"):
        await generate_api_key(session, "bad", "superadmin")


@pytest.mark.asyncio
async def test_validate_api_key_returns_active_key():
    session = AsyncMock()
    key = SimpleNamespace(is_active=True, expires_at=None, last_used_at=None)
    session.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: key)
    result = await validate_api_key(session, "datum_rw_test")
    assert result is key
    assert key.last_used_at is not None


@pytest.mark.asyncio
async def test_validate_api_key_rejects_inactive_or_expired_key():
    session = AsyncMock()
    inactive = SimpleNamespace(is_active=False, expires_at=None, last_used_at=None)
    session.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: inactive)
    assert await validate_api_key(session, "datum_rw_test") is None

    expired = SimpleNamespace(
        is_active=True,
        expires_at=datetime.now(UTC) - timedelta(days=1),
        last_used_at=None,
    )
    session.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: expired)
    assert await validate_api_key(session, "datum_rw_test") is None


@pytest.mark.asyncio
async def test_revoke_and_list_api_keys():
    session = AsyncMock()
    key = SimpleNamespace(is_active=True)
    session.get.return_value = key
    assert await revoke_api_key(session, "key-1") is True
    assert key.is_active is False

    session.execute.return_value = SimpleNamespace(
        scalars=lambda: SimpleNamespace(all=lambda: [key])
    )
    keys = await list_api_keys(session)
    assert keys == [key]
