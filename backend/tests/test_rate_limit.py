from collections import defaultdict

import pytest
from app.rate_limit import InMemoryRateLimiter, RedisRateLimiter, create_rate_limiter
from app.routers import auth, emergency
from fastapi import HTTPException
from redis.exceptions import ConnectionError as RedisConnectionError

from test_phase1 import ORIGIN, register


class FakeRedis:
    def __init__(self) -> None:
        self.counts: dict[str, int] = defaultdict(int)
        self.calls: list[tuple[str, int, str, int]] = []
        self.error: Exception | None = None

    def eval(self, script: str, numkeys: int, key: str, window: int) -> int:
        self.calls.append((script, numkeys, key, window))
        if self.error:
            raise self.error
        self.counts[key] += 1
        return self.counts[key]


def test_redis_backend_uses_atomic_increment_and_expiry_and_enforces_limit():
    client = FakeRedis()
    limiter = RedisRateLimiter(client)  # type: ignore[arg-type]

    limiter.check("login:192.0.2.15", 1, 60, "Too many login attempts")
    with pytest.raises(HTTPException) as blocked:
        limiter.check("login:192.0.2.15", 1, 60, "Too many login attempts")

    assert blocked.value.status_code == 429
    assert blocked.value.detail == "Too many login attempts"
    assert blocked.value.headers == {"Retry-After": "60"}
    script, numkeys, stored_key, window = client.calls[0]
    assert "redis.call('INCR'" in script
    assert "redis.call('EXPIRE'" in script
    assert numkeys == 1
    assert window == 60
    assert "192.0.2.15" not in stored_key


def test_redis_unavailable_fails_closed_by_default():
    limiter = RedisRateLimiter(FakeRedis())
    limiter.client.error = RedisConnectionError("secret-free fake failure")  # type: ignore[attr-defined]

    with pytest.raises(HTTPException) as unavailable:
        limiter.check("login:client", 2, 60)

    assert unavailable.value.status_code == 503
    assert "Authentication services" in unavailable.value.detail


def test_public_emergency_limiter_can_fail_open_when_redis_is_unavailable():
    limiter = RedisRateLimiter(FakeRedis())
    limiter.client.error = RedisConnectionError("secret-free fake failure")  # type: ignore[attr-defined]

    limiter.check("public-emergency:client", 30, 60, fail_open=True)


def test_auth_endpoint_fails_closed_when_shared_store_is_down(client, monkeypatch):
    limiter = RedisRateLimiter(FakeRedis())
    limiter.client.error = RedisConnectionError("secret-free fake failure")  # type: ignore[attr-defined]
    monkeypatch.setattr(auth, "auth_rate_limiter", limiter)

    response = client.post(
        "/api/auth/register",
        headers=ORIGIN,
        json={
            "full_name": "Rate Limit Patient",
            "email": "redis-auth-down@example.com",
            "password": "Safe-demo-passphrase-42",
            "terms_accepted": True,
            "privacy_acknowledged": True,
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"].startswith("Authentication services")


def test_public_emergency_endpoint_continues_when_shared_store_is_down(client, monkeypatch):
    assert register(client, "redis-public@example.com").status_code == 201
    share = client.post(
        "/api/emergency/shares",
        headers=ORIGIN,
        json={"fields": ["full_name"], "expires_in_hours": 1, "consent": True},
    )
    assert share.status_code == 201
    token = share.json()["url"].rsplit("/", maxsplit=1)[-1]

    limiter = RedisRateLimiter(FakeRedis())
    limiter.client.error = RedisConnectionError("secret-free fake failure")  # type: ignore[attr-defined]
    monkeypatch.setattr(emergency, "auth_rate_limiter", limiter)
    response = client.get(f"/api/public/emergency/{token}")

    assert response.status_code == 200
    assert response.json()["full_name"] == "Test Patient"


def test_limiter_factory_uses_redis_when_configured_and_memory_by_default():
    assert isinstance(create_rate_limiter(""), InMemoryRateLimiter)
    assert isinstance(create_rate_limiter("redis://localhost:6379/0"), RedisRateLimiter)
