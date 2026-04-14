"""Small in-memory sliding-window rate limiter for keyed API access."""

from __future__ import annotations

import time
from collections import defaultdict


class RateLimiter:
    def __init__(self, *, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    def _cleanup(self, key: str) -> None:
        cutoff = time.time() - self.window_seconds
        self._requests[key] = [stamp for stamp in self._requests[key] if stamp > cutoff]

    def check(self, key: str) -> bool:
        self._cleanup(key)
        if len(self._requests[key]) >= self.max_requests:
            return False
        self._requests[key].append(time.time())
        return True

    def remaining(self, key: str) -> int:
        self._cleanup(key)
        return max(0, self.max_requests - len(self._requests[key]))
