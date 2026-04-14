from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from datum.services.auth import extract_api_key, require_scope


@pytest.mark.asyncio
async def test_extract_api_key_accepts_header_or_query_param():
    session = AsyncMock()
    mock_key = object()
    with patch(
        "datum.services.auth.validate_api_key",
        new_callable=AsyncMock,
        return_value=mock_key,
    ):
        assert await extract_api_key("datum_rw_header", None, session) is mock_key
        assert await extract_api_key(None, "datum_rw_query", session) is mock_key


@pytest.mark.asyncio
async def test_extract_api_key_returns_none_for_missing_or_invalid_key():
    session = AsyncMock()
    assert await extract_api_key(None, None, session) is None
    with patch(
        "datum.services.auth.validate_api_key",
        new_callable=AsyncMock,
        return_value=None,
    ):
        assert await extract_api_key("datum_rw_bad", None, session) is None


def test_require_scope_enforces_scope():
    checker = require_scope("admin")
    with pytest.raises(HTTPException) as missing:
        checker(None)
    assert missing.value.status_code == 401

    with pytest.raises(HTTPException) as forbidden:
        checker(type("Key", (), {"scope": "read"})())
    assert forbidden.value.status_code == 403

    allowed = checker(type("Key", (), {"scope": "admin"})())
    assert allowed.scope == "admin"
