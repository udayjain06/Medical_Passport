from app.main import app
from fastapi.testclient import TestClient

from test_phase1 import ORIGIN, register


def test_timeline_filters_edit_conflict_uncertainty_and_delete(client: TestClient):
    assert register(client, "timeline@example.com", "Timeline Owner").status_code == 201
    first = client.post(
        "/api/timeline",
        headers=ORIGIN,
        json={
            "title": "Blood panel",
            "category": "Lab test",
            "event_date": "2025-02-03",
            "summary": "Initial note",
        },
    )
    second = client.post(
        "/api/timeline",
        headers=ORIGIN,
        json={
            "title": "Medication amount unclear",
            "category": "Prescription",
            "event_date": "2025-06-10",
            "verification_status": "uncertain",
            "uncertainty_note": "Two records show different quantities.",
        },
    )
    assert first.status_code == 201 and second.status_code == 201
    assert len(client.get("/api/timeline", params={"category": "Lab test"}).json()) == 1
    assert (
        len(
            client.get(
                "/api/timeline", params={"date_from": "2025-02-01", "date_to": "2025-03-01"}
            ).json()
        )
        == 1
    )
    assert (
        client.get("/api/timeline", params={"verification_status": "uncertain"})
        .json()[0]["uncertainty_note"]
        .startswith("Two records")
    )
    assert (
        client.get(
            "/api/timeline", params={"date_from": "2025-07-01", "date_to": "2025-01-01"}
        ).status_code
        == 422
    )

    updated = client.put(
        f"/api/timeline/{first.json()['id']}",
        headers=ORIGIN,
        json={
            "title": "Blood panel reviewed",
            "category": "Lab test",
            "event_date": "2025-02-03",
            "verification_status": "conflict",
            "conflict_group": "lab-value-review-1",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["conflict_group"] == "lab-value-review-1"
    assert (
        client.post(
            "/api/timeline",
            headers=ORIGIN,
            json={
                "title": "Invalid conflict",
                "category": "Lab test",
                "verification_status": "conflict",
            },
        ).status_code
        == 422
    )
    assert client.delete(f"/api/timeline/{second.json()['id']}", headers=ORIGIN).status_code == 204
    assert len(client.get("/api/timeline").json()) == 1


def test_timeline_write_permissions_are_profile_scoped(client: TestClient):
    assert register(client, "timeline-owner@example.com", "Owner").status_code == 201
    profile_id = client.get("/api/profile").json()["id"]
    event = client.post(
        "/api/timeline",
        headers=ORIGIN,
        json={"title": "Private event", "category": "Consultation"},
    ).json()
    with TestClient(app, headers=ORIGIN) as viewer:
        assert register(viewer, "timeline-viewer@example.com", "Viewer").status_code == 201
        assert (
            client.post(
                f"/api/profiles/{profile_id}/access",
                headers=ORIGIN,
                json={"email": "timeline-viewer@example.com", "role": "viewer"},
            ).status_code
            == 201
        )
        headers = {"Origin": "http://localhost:3000", "X-Patient-Profile": profile_id}
        listed = viewer.get("/api/timeline", headers={"X-Patient-Profile": profile_id}).json()
        assert listed[0]["can_edit"] is False
        assert viewer.delete(f"/api/timeline/{event['id']}", headers=headers).status_code == 403
