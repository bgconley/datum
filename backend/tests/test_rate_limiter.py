"""Tests for rate limiting."""

from datum.services.rate_limiter import RateLimiter


def test_rate_limiter_allows_within_limit():
    limiter = RateLimiter(max_requests=2, window_seconds=60)
    assert limiter.check("key-1") is True
    assert limiter.check("key-1") is True
    assert limiter.check("key-1") is False


def test_rate_limiter_tracks_remaining():
    limiter = RateLimiter(max_requests=3, window_seconds=60)
    limiter.check("key-1")
    assert limiter.remaining("key-1") == 2
