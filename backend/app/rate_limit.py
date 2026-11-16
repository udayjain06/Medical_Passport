from __future__ import annotations

import hashlib
import logging
from collections import defaultdict, deque
from threading import Lock
from time import monotonic
from typing import Protocol

from fastapi import HTTPException
from redis import Redis
from redis.exceptions import RedisError

from app.config import settings

logger = logging.getLogger(__name__)

_INCREMENT_WITH_FIRST_HIT_EXPIRY = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return count
"""


class RateLimiter(Protocol):
    def check(
        self,
        key: str,
        limit: int,
        window_seconds: int,
        message: str = "Too many requests. Try again later.",
        *,
        fail_open: bool = False,
    ) -> None: ...


class InMemoryRateLimiter:
    """Single-process limiter for local development and tests."""

    def __init__(self) -> None:
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(
        self,
        key: str,
        limit: int,
        window_seconds: int,
        message: str = "Too many requests. Try again later.",
        *,
        fail_open: bool = False,
    ) -> None:
        del fail_open
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
                    detail=message,
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


class RedisRateLimiter:
    """Shared limiter using one atomic Redis INCR/EXPIRE script per request."""

    def __init__(self, client: Redis) -> None:
        self.client = client

    @classmethod
    def from_url(cls, url: str) -> RedisRateLimiter:
        client = Redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        return cls(client)

    def check(
        self,
        key: str,
        limit: int,
        window_seconds: int,
        message: str = "Too many requests. Try again later.",
        *,
        fail_open: bool = False,
    ) -> None:
        # Do not persist raw limiter keys, which may contain a client IP address.
        storage_key = f"medical-passport:rate:{hashlib.sha256(key.encode()).hexdigest()}"
        try:
            count = int(
                self.client.eval(
                    _INCREMENT_WITH_FIRST_HIT_EXPIRY,
                    1,
                    storage_key,
                    max(1, window_seconds),
                )
            )
        except RedisError:
            logger.error("shared_rate_limit_unavailable fail_open=%s", fail_open)
            if fail_open:
                return
            raise HTTPException(
                status_code=503,
                detail="Authentication services are temporarily unavailable. Try again.",
            ) from None

        if count > limit:
            raise HTTPException(
                status_code=429,
                detail=message,
                headers={"Retry-After": str(max(1, window_seconds))},
            )


def create_rate_limiter(redis_url: str | None = None) -> RateLimiter:
    configured_url = redis_url if redis_url is not None else settings.redis_url
    if configured_url:
        return RedisRateLimiter.from_url(configured_url)
    return InMemoryRateLimiter()


auth_rate_limiter = create_rate_limiter()
