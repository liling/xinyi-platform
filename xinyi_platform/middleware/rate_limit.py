import time
from collections import defaultdict

from fastapi import HTTPException, Request, status


class InMemoryRateLimiter:
    """Per-IP, per-window counter. Single-process only."""

    def __init__(self, max_requests: int, window_seconds: int = 60):
        self.max = max_requests
        self.window = window_seconds
        self._buckets: dict[str, list[float]] = defaultdict(list)
        self._current_window = int(time.time() // self.window)

    def _reset_if_needed(self) -> None:
        now_window = int(time.time() // self.window)
        if now_window != self._current_window:
            self._buckets.clear()
            self._current_window = now_window

    async def __call__(self, request: Request) -> None:
        self._reset_if_needed()
        ip = request.client.host if request.client else "unknown"
        now = time.time()
        bucket = self._buckets[ip]
        self._buckets[ip] = [t for t in bucket if now - t < self.window]
        if len(self._buckets[ip]) >= self.max:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
            )
        self._buckets[ip].append(now)


def make_limiter(max_per_minute: int) -> InMemoryRateLimiter:
    return InMemoryRateLimiter(max_per_minute, 60)


login_limiter = make_limiter(5)
register_limiter = make_limiter(3)
password_reset_limiter = make_limiter(3)
