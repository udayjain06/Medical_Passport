from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

from app.auth_tokens import token_hash
from app.config import settings
from app.models import AuthActionToken
from fastapi.testclient import TestClient

from test_phase1 import ORIGIN, register


def _register_unverified(client: TestClient, email: str):
    return client.post(
        "/api/auth/register",
        headers=ORIGIN,
        json={
            "full_name": "Unverified Patient",
            "email": email,
            "password": "Safe-demo-passphrase-42",
            "terms_consent": True,
            "privacy_consent": True,
        },
    )


def _latest_verification_token(client: TestClient, email: str) -> str:
    message = next(
        item
        for item in reversed(client.app.state.test_email_messages)
        if item.recipient.lower() == email.lower()
    )
    link = next(line for line in message.text_body.splitlines() if line.startswith("http"))
    return parse_qs(urlsplit(link).query)["token"][0]


def test_verification_token_is_hashed_single_use_and_gates_sharing(client):
    email = "unverified@example.com"
    response = _register_unverified(client, email)
    assert response.status_code == 201
    assert response.json()["user"]["email_verified_at"] is None
    token = _latest_verification_token(client, email)

    with client.app.state.test_sessions() as db:
        stored = db.query(AuthActionToken).one()
        assert stored.token_hash == token_hash(token)
        assert token not in stored.token_hash
        assert stored.expires_at.replace(tzinfo=UTC) > datetime.now(UTC)

    profile_id = client.get("/api/profile").json()["id"]
    share_body = {"fields": ["full_name"], "expires_in_hours": 24, "consent": True}
    denied_share = client.post("/api/emergency/shares", headers=ORIGIN, json=share_body)
    assert denied_share.status_code == 403
    denied_grant = client.post(
        f"/api/profiles/{profile_id}/access",
        headers=ORIGIN,
        json={"email": "future-family@example.com", "role": "viewer"},
    )
    assert denied_grant.status_code == 403

    verified = client.post("/api/auth/verify-email", headers=ORIGIN, json={"token": token})
    assert verified.status_code == 200
    assert client.get("/api/auth/me").json()["email_verified_at"]
    assert (
        client.post("/api/auth/verify-email", headers=ORIGIN, json={"token": token}).status_code
        == 400
    )
    assert client.post("/api/emergency/shares", headers=ORIGIN, json=share_body).status_code == 201

    with TestClient(client.app, headers=ORIGIN) as family_client:
        assert register(family_client, "verified-target@example.com").status_code == 201
    grant = client.post(
        f"/api/profiles/{profile_id}/access",
        headers=ORIGIN,
        json={"email": "verified-target@example.com", "role": "viewer"},
    )
    assert grant.status_code == 201


def test_expired_verification_token_cannot_be_used(client):
    email = "expired-verification@example.com"
    assert _register_unverified(client, email).status_code == 201
    token = _latest_verification_token(client, email)
    with client.app.state.test_sessions() as db:
        stored = db.query(AuthActionToken).filter_by(token_hash=token_hash(token)).one()
        stored.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()

    response = client.post("/api/auth/verify-email", headers=ORIGIN, json={"token": token})
    assert response.status_code == 400
    assert client.get("/api/auth/me").json()["email_verified_at"] is None


def test_resend_verification_rotates_and_invalidates_prior_token(client):
    email = "resend-verification@example.com"
    assert _register_unverified(client, email).status_code == 201
    old_token = _latest_verification_token(client, email)

    response = client.post("/api/auth/resend-verification", headers=ORIGIN)
    assert response.status_code == 200
    assert response.json() == {
        "message": "If this account needs verification, instructions will be sent."
    }
    new_token = _latest_verification_token(client, email)
    assert new_token != old_token
    assert (
        client.post("/api/auth/verify-email", headers=ORIGIN, json={"token": old_token}).status_code
        == 400
    )
    assert (
        client.post("/api/auth/verify-email", headers=ORIGIN, json={"token": new_token}).status_code
        == 200
    )


def test_resend_verification_requires_session(client):
    response = client.post("/api/auth/resend-verification", headers=ORIGIN)
    assert response.status_code == 401


def test_resend_verification_is_rate_limited(client, monkeypatch):
    monkeypatch.setattr(settings, "auth_rate_limit_count", 1)
    assert _register_unverified(client, "resend-rate-limit@example.com").status_code == 201

    first = client.post("/api/auth/resend-verification", headers=ORIGIN)
    second = client.post("/api/auth/resend-verification", headers=ORIGIN)

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers["retry-after"]


def test_email_link_test_hook_requires_explicit_test_configuration(client, monkeypatch):
    assert register(client, "test-hook@example.com").status_code == 201
    import app.routers.auth as auth_router

    synthetic_link = "http://localhost/verify-email?token=synthetic-only"
    monkeypatch.setattr(auth_router, "take_test_email_link", lambda *_args: synthetic_link)
    monkeypatch.setattr(settings, "app_env", "test")
    monkeypatch.setattr(settings, "email_test_hook_enabled", True)
    response = client.get("/api/auth/test/email-link?purpose=email_verification")
    assert response.status_code == 200
    assert response.json() == {"url": synthetic_link}

    monkeypatch.setattr(settings, "app_env", "development")
    assert client.get("/api/auth/test/email-link").status_code == 404
