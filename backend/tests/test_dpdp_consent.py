from datetime import UTC, datetime

from app.models import AuditEvent, ConsentRecord, EmergencyShare
from sqlalchemy import select

from test_phase1 import ORIGIN, register


def test_signup_requires_and_records_terms_and_privacy_consent(client):
    missing = client.post(
        "/api/auth/register",
        headers=ORIGIN,
        json={
            "full_name": "Consent Patient",
            "email": "missing-consent@example.com",
            "password": "Safe-demo-passphrase-42",
        },
    )
    assert missing.status_code == 422

    denied = client.post(
        "/api/auth/register",
        headers=ORIGIN,
        json={
            "full_name": "Consent Patient",
            "email": "denied-consent@example.com",
            "password": "Safe-demo-passphrase-42",
            "terms_accepted": True,
            "privacy_acknowledged": False,
        },
    )
    assert denied.status_code == 422

    registered = register(client, "consent@example.com")
    assert registered.status_code == 201
    records = client.get("/api/auth/consents")
    assert records.status_code == 200
    assert {record["purpose"] for record in records.json()} == {"terms", "privacy"}
    assert all(
        record["version"] == "v1" and record["withdrawn_at"] is None for record in records.json()
    )


def test_withdrawing_emergency_consent_revokes_active_links(client):
    assert register(client, "withdraw@example.com").status_code == 201
    response = client.post(
        "/api/emergency/shares",
        headers=ORIGIN,
        json={"fields": ["full_name"], "expires_in_hours": 1, "consent": True},
    )
    assert response.status_code == 201, response.text
    token = response.json()["url"].rsplit("/", maxsplit=1)[-1]

    consent = client.get("/api/auth/consents").json()
    emergency = [record for record in consent if record["purpose"] == "emergency_sharing"]
    assert len(emergency) == 1
    assert emergency[0]["withdrawn_at"] is None

    withdrawn = client.post("/api/auth/consents/emergency_sharing/withdraw")
    assert withdrawn.status_code == 200
    assert withdrawn.json() == {"withdrawn_records": 1, "revoked_links": 1}
    assert client.get(f"/api/public/emergency/{token}").status_code == 404
    assert any(
        record["withdrawn_at"]
        for record in client.get("/api/auth/consents").json()
        if record["purpose"] == "emergency_sharing"
    )

    with client.app.state.test_sessions() as db:
        share = db.scalar(select(EmergencyShare))
        assert share is not None and share.revoked_at is not None


def test_terms_and_privacy_consent_cannot_be_withdrawn(client):
    assert register(client, "no-withdraw@example.com").status_code == 201
    assert client.post("/api/auth/consents/terms/withdraw").status_code == 409
    assert client.post("/api/auth/consents/privacy/withdraw").status_code == 409


def test_audit_log_is_owner_scoped_limited_and_payload_free(client):
    registered = register(client, "audit-owner@example.com")
    assert registered.status_code == 201
    owner_id = registered.json()["user"]["id"]

    with client.app.state.test_sessions() as db:
        from uuid import UUID

        db.add_all(
            [
                AuditEvent(
                    user_id=UUID(owner_id),
                    action=f"test.event_{index}",
                    target_type="secret-type-not-exposed",
                    target_id=None,
                    created_at=datetime.now(UTC),
                )
                for index in range(105)
            ]
        )
        db.commit()

    response = client.get("/api/auth/audit-log")
    assert response.status_code == 200
    assert len(response.json()) == 100
    assert all(set(item) == {"time", "action"} for item in response.json())
    assert all("secret" not in str(item).lower() for item in response.json())

    with client.app.state.test_sessions() as db:
        users = db.scalars(select(ConsentRecord.user_id).distinct()).all()
        assert users == [UUID(owner_id)]
