import asyncio
import time


class TokenBucket:
    def __init__(self, rate_per_minute: float, burst: float) -> None:
        self._rate_per_sec = rate_per_minute / 60.0
        self._capacity = burst
        self._tokens = burst
        self._last = time.monotonic()
        self._lock = asyncio.Lock()

    async def try_acquire(self) -> tuple[bool, float]:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last
            self._tokens = min(self._capacity, self._tokens + elapsed * self._rate_per_sec)
            self._last = now
            if self._tokens >= 1:
                self._tokens -= 1
                return True, 0.0
            deficit = 1 - self._tokens
            retry_after = deficit / self._rate_per_sec
            return False, retry_after


_bucket: TokenBucket | None = None


def get_rate_limiter() -> TokenBucket:
    global _bucket
    if _bucket is None:
        from app.core.config import RATE_LIMIT_BURST, RATE_LIMIT_PER_MINUTE

        _bucket = TokenBucket(RATE_LIMIT_PER_MINUTE, RATE_LIMIT_BURST)
    return _bucket
