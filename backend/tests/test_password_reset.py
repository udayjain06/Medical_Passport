from datetime import UTC, datetime, timedelta
from time import perf_counter
from urllib.parse import parse_qs, urlsplit

from app.auth_tokens import token_hash
from app.config import settings
from app.models import AuditEvent, AuthActionToken
from fastapi.testclient import TestClient

from test_phase1 import ORIGIN, PASSWORD, register


def _latest_reset_token(client: TestClient, email: str) -> str:
    message = next(
        item
        for item in reversed(client.app.state.test_email_messages)
        if item.recipient.lower() == email.lower() and item.purpose == "password_reset"
    )
    link = next(line for line in message.text_body.splitlines() if line.startswith("http"))
    return parse_qs(urlsplit(link).query)["token"][0]


def _request_reset(client: TestClient, email: str):
    return client.post("/api/auth/forgot-password", headers=ORIGIN, json={"email": email})


def test_forgot_password_does_not_enumerate_accounts_and_stores_only_hash(client):
    email = "reset-owner@example.com"
    assert register(client, email).status_code == 201

    started = perf_counter()
    existing = _request_reset(client, email)
    existing_elapsed = perf_counter() - started
    started = perf_counter()
    missing = _request_reset(client, "missing-reset@example.com")
    missing_elapsed = perf_counter() - started
    assert existing.status_code == missing.status_code == 200
    assert (
        existing.json()
        == missing.json()
        == {"message": "If an account exists, password reset instructions will be sent."}
    )
    minimum = settings.auth_uniform_response_ms / 1000 * 0.95
    assert existing_elapsed >= minimum
    assert missing_elapsed >= minimum

    token = _latest_reset_token(client, email)
    with client.app.state.test_sessions() as db:
        stored = db.query(AuthActionToken).filter_by(purpose="password_reset").one()
        assert stored.token_hash == token_hash(token)
        assert token not in stored.token_hash
        assert stored.expires_at.replace(tzinfo=UTC) > datetime.now(UTC)
        actions = db.query(AuditEvent).filter_by(action="auth.password_reset.requested").all()
        assert len(actions) == 2


def test_password_reset_invalidates_all_sessions_and_token_is_single_use(client):
    email = "session-reset@example.com"
    assert register(client, email).status_code == 201
    with TestClient(client.app, headers=ORIGIN) as second_session:
        login = second_session.post(
            "/api/auth/login", headers=ORIGIN, json={"email": email, "password": PASSWORD}
        )
        assert login.status_code == 200
        assert second_session.get("/api/auth/me").status_code == 200

    assert _request_reset(client, email).status_code == 200
    token = _latest_reset_token(client, email)
    reset = client.post(
        "/api/auth/reset-password",
        headers=ORIGIN,
        json={"token": token, "password": "New-safe-demo-passphrase-77"},
    )
    assert reset.status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    assert second_session.get("/api/auth/me").status_code == 401
    assert (
        client.post(
            "/api/auth/reset-password",
            headers=ORIGIN,
            json={"token": token, "password": "Another-safe-demo-passphrase-88"},
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/auth/login",
            headers=ORIGIN,
            json={"email": email, "password": PASSWORD},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/login",
            headers=ORIGIN,
            json={"email": email, "password": "New-safe-demo-passphrase-77"},
        ).status_code
        == 200
    )


def test_expired_reset_token_and_weak_replacement_are_rejected(client):
    email = "expired-reset@example.com"
    assert register(client, email).status_code == 201
    assert _request_reset(client, email).status_code == 200
    token = _latest_reset_token(client, email)
    weak = client.post(
        "/api/auth/reset-password", headers=ORIGIN, json={"token": token, "password": "short"}
    )
    assert weak.status_code == 422

    with client.app.state.test_sessions() as db:
        stored = db.query(AuthActionToken).filter_by(token_hash=token_hash(token)).one()
        stored.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()

    expired = client.post(
        "/api/auth/reset-password",
        headers=ORIGIN,
        json={"token": token, "password": "Replacement-safe-passphrase-93"},
    )
    assert expired.status_code == 400
    assert client.get("/api/auth/me").status_code == 200
