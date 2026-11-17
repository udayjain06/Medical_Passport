import asyncio
import importlib
import json
import logging

from app.logging_config import JsonFormatter, redact_message, request_id_context
from app.request_limits import RequestSizeLimitMiddleware
from fastapi.testclient import TestClient

from test_phase1 import ORIGIN, register


def test_health_aliases_and_api_security_headers(client: TestClient):
    live = client.get("/healthz")
    ready = client.get("/readyz")

    assert live.status_code == 200 and live.json() == {"status": "ok"}
    assert ready.status_code == 200 and ready.json()["database"] == "ok"
    assert live.headers["cache-control"] == "no-store, private"
    assert live.headers["x-content-type-options"] == "nosniff"
    assert "frame-ancestors 'none'" in live.headers["content-security-policy"]
    assert live.headers["permissions-policy"] == "camera=(self), microphone=(), geolocation=()"
    assert live.headers["x-request-id"]


def test_api_documentation_routes_are_disabled_in_production(monkeypatch):
    import app.main as main

    monkeypatch.setattr(main.settings, "app_env", "production")
    production_main = importlib.reload(main)
    with TestClient(production_main.app) as production_client:
        assert production_client.get("/docs").status_code == 404
        assert production_client.get("/redoc").status_code == 404
        assert production_client.get("/openapi.json").status_code == 404


def test_public_emergency_response_is_no_store_and_has_no_referrer(client: TestClient):
    assert register(client, "headers-emergency@example.com").status_code == 201
    share = client.post(
        "/api/emergency/shares",
        headers=ORIGIN,
        json={"fields": ["full_name"], "expires_in_hours": 1, "consent": True},
    )
    token = share.json()["url"].rsplit("/", maxsplit=1)[-1]

    response = client.get(f"/api/public/emergency/{token}")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, private"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-robots-tag"] == "noindex, nofollow, noarchive"


def test_request_body_limit_rejects_chunked_oversize_and_replays_valid_body():
    async def run_oversize() -> list[dict]:
        messages = [
            {"type": "http.request", "body": b"1234", "more_body": True},
            {"type": "http.request", "body": b"5678", "more_body": False},
        ]
        sent: list[dict] = []

        async def receive():
            return messages.pop(0)

        async def unreachable_app(_scope, _receive, _send):
            raise AssertionError("oversized body reached the application")

        async def send(message):
            sent.append(message)

        await RequestSizeLimitMiddleware(unreachable_app, max_bytes=6)(
            {"type": "http", "method": "POST", "headers": []}, receive, send
        )
        return sent

    async def run_valid() -> tuple[bytes, list[dict]]:
        sent: list[dict] = []
        messages = [{"type": "http.request", "body": b"12345", "more_body": False}]
        observed = b""

        async def receive():
            return messages.pop(0) if messages else {"type": "http.disconnect"}

        async def downstream(_scope, downstream_receive, downstream_send):
            nonlocal observed
            observed = (await downstream_receive())["body"]
            await downstream_send({"type": "http.response.start", "status": 200, "headers": []})
            await downstream_send({"type": "http.response.body", "body": b"ok"})

        async def send(message):
            sent.append(message)

        await RequestSizeLimitMiddleware(downstream, max_bytes=6)(
            {"type": "http", "method": "POST", "headers": []}, receive, send
        )
        return observed, sent

    oversize = asyncio.run(run_oversize())
    assert oversize[0]["status"] == 413
    assert json.loads(oversize[1]["body"])["detail"] == "Request body exceeds configured size limit"
    observed, valid_response = asyncio.run(run_valid())
    assert observed == b"12345"
    assert valid_response[0]["status"] == 200


def test_log_formatter_redacts_tokens_ips_and_passwords():
    token = "a" * 43
    message = f'GET /api/public/emergency/{token} client=192.0.2.10 password="private-value"'
    safe = redact_message(message)
    assert token not in safe
    assert "192.0.2.10" not in safe
    assert "private-value" not in safe
    assert "2001:db8::1" not in redact_message("remote=2001:db8::1")

    context_token = request_id_context.set("request-123")
    try:
        record = logging.LogRecord("api", logging.INFO, "", 0, message, (), None)
        formatted = json.loads(JsonFormatter().format(record))
    finally:
        request_id_context.reset(context_token)
    assert formatted["request_id"] == "request-123"
    assert token not in formatted["message"]
    assert "192.0.2.10" not in formatted["message"]
