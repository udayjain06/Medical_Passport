from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from fastapi import HTTPException


class InMemoryRateLimiter:
    """Single-process limiter for development; production needs a shared store."""

    def __init__(self) -> None:
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str, limit: int, window_seconds: int) -> None:
        now = monotonic()
        cutoff = now - window_seconds
        with self._lock:
            requests = self._requests[key]
            while requests and requests[0] <= cutoff:
                requests.popleft()
            if len(requests) >= limit:
                retry_after = max(1, int(window_seconds - (now - requests[0])))
                raise HTTPException(
                    status_code=429,
                    detail="Too many authentication attempts. Try again later.",
                    headers={"Retry-After": str(retry_after)},
                )
            requests.append(now)
            if len(self._requests) > 1000:
                expired = [
                    name
                    for name, values in self._requests.items()
                    if not values or values[-1] <= cutoff
                ]
                for name in expired:
                    self._requests.pop(name, None)


auth_rate_limiter = InMemoryRateLimiter()
