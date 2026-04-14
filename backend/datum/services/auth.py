"""FastAPI authentication dependencies for scoped API keys."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from datum.config import settings
from datum.db import get_session
from datum.models.agent import ApiKey
from datum.services.api_keys import has_scope, validate_api_key
from datum.services.rate_limiter import RateLimiter

_rate_limiter = RateLimiter(
    max_requests=settings.api_rate_limit_requests,
    window_seconds=settings.api_rate_limit_window_seconds,
)


async def extract_api_key(
    x_api_key: Annotated[str | None, Header()] = None,
    api_key: Annotated[str | None, Query()] = None,
    session: AsyncSession = Depends(get_session),
) -> ApiKey | None:
    """Extract and validate an API key from header or query param."""
    raw_key = x_api_key or api_key
    if not raw_key:
        return None
    return await validate_api_key(session, raw_key)


def require_scope(scope: str):
    """Require a validated API key with at least the requested scope."""

    def checker(api_key: ApiKey | None = Depends(extract_api_key)) -> ApiKey:
        if api_key is None:
            raise HTTPException(status_code=401, detail="API key required")
        if not has_scope(api_key, scope):
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient scope: requires '{scope}', key has '{api_key.scope}'",
            )
        return api_key

    return checker


def require_rate_limit():
    """Optionally enforce per-key rate limiting for agent/admin surfaces."""

    async def checker(api_key: ApiKey | None = Depends(extract_api_key)) -> None:
        if api_key is None:
            return
        if _rate_limiter.check(str(api_key.id)):
            return
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Try again later.",
            headers={"Retry-After": str(settings.api_rate_limit_window_seconds)},
        )

    return checker
