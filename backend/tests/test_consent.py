from test_phase1 import ORIGIN, register


def test_signup_records_terms_and_privacy_consents(client):
    assert register(client, "consent@example.com").status_code == 201
    consents = client.get("/api/privacy/consents").json()
    assert {item["purpose"] for item in consents} == {"terms", "privacy"}
    assert all(item["version"] == "v1" and item["withdrawn_at"] is None for item in consents)


def test_emergency_consent_withdrawal_revokes_all_active_links(client):
    assert register(client, "withdraw@example.com").status_code == 201
    created = client.post(
        "/api/emergency/shares",
        headers=ORIGIN,
        json={"fields": ["full_name"], "expires_in_hours": 24, "consent": True},
    )
    assert created.status_code == 201, created.text
    token = created.json()["url"].rsplit("/", 1)[-1]
    assert client.get(f"/api/public/emergency/{token}").status_code == 200
    consents = client.get("/api/privacy/consents").json()
    assert any(item["purpose"] == "emergency_sharing" for item in consents)
    withdrawn = client.post("/api/privacy/consents/emergency_sharing/withdraw")
    assert withdrawn.status_code == 200
    assert withdrawn.json()["revoked_links"] == 1
    assert client.get(f"/api/public/emergency/{token}").status_code == 404
    assert client.post("/api/privacy/consents/terms/withdraw").status_code == 422


def test_account_audit_view_has_only_time_and_action(client):
    assert register(client, "audit@example.com").status_code == 201
    events = client.get("/api/privacy/audit").json()
    assert events and set(events[0]) == {"time", "action"}
