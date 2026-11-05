from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from test_phase1 import ORIGIN, register


def test_emergency_consent_qr_fields_and_revocation(client: TestClient):
    assert register(client, "emergency@example.com").status_code == 201
    client.put(
        "/api/profile",
        headers=ORIGIN,
        json={
            "full_name": "Synthetic Patient",
            "blood_group": "O+",
            "known_allergies": "Synthetic allergy",
            "major_conditions": "",
            "current_medications": "",
            "emergency_contacts": [],
        },
    )
    denied = client.post(
        "/api/emergency/shares",
        headers=ORIGIN,
        json={"fields": ["full_name"], "expires_in_hours": 1, "consent": False},
    )
    assert denied.status_code == 422
    created = client.post(
        "/api/emergency/shares",
        headers=ORIGIN,
        json={"fields": ["full_name", "blood_group"], "expires_in_hours": 1, "consent": True},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["qr_png_data_url"].startswith("data:image/png;base64,")
    token = body["url"].rsplit("/", 1)[-1]
    public = client.get(f"/api/public/emergency/{token}")
    assert public.status_code == 200 and public.json()["full_name"] == "Synthetic Patient"
    assert public.json()["blood_group"] == "O+" and "known_allergies" not in public.json()
    assert client.delete(f"/api/emergency/shares/{body['id']}", headers=ORIGIN).status_code == 204
    assert client.get(f"/api/public/emergency/{token}").status_code == 404


def test_expired_emergency_link_is_unavailable(client: TestClient, monkeypatch):
    import app.routers.emergency as emergency

    assert register(client, "expired@example.com").status_code == 201
    response = client.post(
        "/api/emergency/shares",
        headers=ORIGIN,
        json={"fields": ["full_name"], "expires_in_hours": 1, "consent": True},
    )
    token = response.json()["url"].rsplit("/", 1)[-1]
    original = datetime

    class FutureDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return original.now(tz) + timedelta(hours=2)

    monkeypatch.setattr(emergency, "datetime", FutureDateTime)
    assert client.get(f"/api/public/emergency/{token}").status_code == 404
