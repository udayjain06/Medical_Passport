from app.main import app
from fastapi.testclient import TestClient

from test_phase1 import ORIGIN, register

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF"


def test_family_profile_sharing_switch_and_viewer_permissions(client: TestClient):
    assert register(client, "owner@example.com", "Owner Patient").status_code == 201
    profile_id = client.get("/api/profile").json()["id"]
    owner_document = client.post(
        "/api/documents", headers=ORIGIN, files={"file": ("owner.pdf", PDF, "application/pdf")}
    ).json()
    with TestClient(app, headers=ORIGIN) as family:
        assert register(family, "family@example.com", "Family Patient").status_code == 201
        family_user_id = family.get("/api/auth/me").json()["id"]
        grant = client.post(
            f"/api/profiles/{profile_id}/access",
            headers=ORIGIN,
            json={"email": "family@example.com", "role": "viewer"},
        )
        assert grant.status_code == 201
        listed = family.get("/api/profiles").json()
        shared = next(p for p in listed if p["id"] == profile_id)
        assert shared["role"] == "viewer"
        response = family.get("/api/profile", headers={"X-Patient-Profile": profile_id})
        assert response.status_code == 200 and response.json()["full_name"] == "Owner Patient"
        assert (
            family.get(
                f"/api/documents/{owner_document['id']}/content",
                headers={"X-Patient-Profile": profile_id},
            ).content
            == PDF
        )
        denied_upload = family.post(
            "/api/documents",
            headers={**ORIGIN, "X-Patient-Profile": profile_id},
            files={"file": ("x.pdf", PDF, "application/pdf")},
        )
        assert denied_upload.status_code == 403
        denied = family.put(
            "/api/profile",
            headers={**ORIGIN, "X-Patient-Profile": profile_id},
            json={"full_name": "Changed"},
        )
        assert denied.status_code == 403
    assert (
        client.delete(
            f"/api/profiles/{profile_id}/access/{family_user_id}", headers=ORIGIN
        ).status_code
        == 204
    )
    with TestClient(app, headers=ORIGIN) as family:
        login = family.post(
            "/api/auth/login",
            headers=ORIGIN,
            json={"email": "family@example.com", "password": "Safe-demo-passphrase-42"},
        )
        assert login.status_code == 200
        assert (
            family.get("/api/profile", headers={"X-Patient-Profile": profile_id}).status_code == 404
        )


def test_dependent_profiles_have_independent_profile_and_document_scope(client: TestClient):
    assert register(client, "parent@example.com", "Parent Patient").status_code == 201
    denied = client.post(
        "/api/profiles",
        headers=ORIGIN,
        json={
            "full_name": "Synthetic Child",
            "relationship_label": "Child",
            "authority_confirmed": False,
        },
    )
    assert denied.status_code == 422
    created = client.post(
        "/api/profiles",
        headers=ORIGIN,
        json={
            "full_name": "Synthetic Child",
            "relationship_label": "Child",
            "authority_confirmed": True,
        },
    )
    assert created.status_code == 201
    dependent_id = created.json()["id"]
    assert dependent_id != client.get("/api/profile").json()["id"]
    child = client.get("/api/profile", headers={"X-Patient-Profile": dependent_id})
    assert child.status_code == 200 and child.json()["full_name"] == "Synthetic Child"
    assert client.get("/api/documents", headers={"X-Patient-Profile": dependent_id}).json() == []
    dependent_document = client.post(
        "/api/documents",
        headers={**ORIGIN, "X-Patient-Profile": dependent_id},
        files={"file": ("dependent-only.pdf", PDF, "application/pdf")},
    )
    assert dependent_document.status_code == 201, dependent_document.text
    visible = client.get("/api/documents", headers={"X-Patient-Profile": dependent_id})
    assert [item["id"] for item in visible.json()] == [dependent_document.json()["id"]]
    # Switching back to the owner's profile must not reveal dependent records.
    assert client.get("/api/documents").json() == []


def test_owner_caregiver_viewer_document_access_and_cross_profile_isolation(client: TestClient):
    assert register(client, "owner-docs@example.com", "Owner").status_code == 201
    profile_id = client.get("/api/profile").json()["id"]
    owner_doc = client.post(
        "/api/documents", headers=ORIGIN, files={"file": ("owner.pdf", PDF, "application/pdf")}
    ).json()

    with TestClient(app, headers=ORIGIN) as viewer:
        assert register(viewer, "viewer-docs@example.com", "Viewer").status_code == 201
        viewer_id = viewer.get("/api/auth/me").json()["id"]
        assert (
            client.post(
                f"/api/profiles/{profile_id}/access",
                headers=ORIGIN,
                json={"email": "viewer-docs@example.com", "role": "viewer"},
            ).status_code
            == 201
        )
        headers = {"X-Patient-Profile": profile_id}
        assert [d["id"] for d in viewer.get("/api/documents", headers=headers).json()] == [
            owner_doc["id"]
        ]
        viewer_item = viewer.get("/api/documents", headers=headers).json()[0]
        assert viewer_item["can_edit"] is False
        viewer_details = viewer.get(f"/api/documents/{owner_doc['id']}", headers=headers)
        assert viewer_details.status_code == 200 and viewer_details.json()["can_edit"] is False
        assert (
            viewer.get(f"/api/documents/{owner_doc['id']}/content", headers=headers).content == PDF
        )
        assert (
            viewer.delete(
                f"/api/documents/{owner_doc['id']}", headers={**ORIGIN, **headers}
            ).status_code
            == 403
        )
        assert (
            viewer.patch(
                f"/api/documents/{owner_doc['id']}",
                headers={**ORIGIN, **headers},
                json={"category": "Prescription"},
            ).status_code
            == 403
        )
        assert (
            client.delete(
                f"/api/profiles/{profile_id}/access/{viewer_id}", headers=ORIGIN
            ).status_code
            == 204
        )

    with TestClient(app, headers=ORIGIN) as caregiver:
        assert register(caregiver, "caregiver-docs@example.com", "Caregiver").status_code == 201
        assert (
            client.post(
                f"/api/profiles/{profile_id}/access",
                headers=ORIGIN,
                json={"email": "caregiver-docs@example.com", "role": "caregiver"},
            ).status_code
            == 201
        )
        headers = {"X-Patient-Profile": profile_id}
        listed = caregiver.get("/api/documents", headers=headers)
        assert listed.status_code == 200 and len(listed.json()) == 1
        assert listed.json()[0]["can_edit"] is True
        caregiver_doc = caregiver.post(
            "/api/documents",
            headers={**ORIGIN, **headers},
            files={"file": ("caregiver.pdf", PDF, "application/pdf")},
        )
        assert caregiver_doc.status_code == 201
        assert len(client.get("/api/documents").json()) == 2

    with TestClient(app, headers=ORIGIN) as stranger:
        assert register(stranger, "stranger-docs@example.com", "Stranger").status_code == 201
        headers = {"X-Patient-Profile": profile_id}
        assert stranger.get("/api/documents", headers=headers).status_code == 404
        assert stranger.get(f"/api/documents/{owner_doc['id']}", headers=headers).status_code == 404


def test_archiving_dependent_retains_records_and_revokes_access_and_shares(client: TestClient):
    assert register(client, "archive-owner@example.com", "Owner").status_code == 201
    primary_id = client.get("/api/profile").json()["id"]
    child = client.post(
        "/api/profiles",
        headers=ORIGIN,
        json={
            "full_name": "Archived Synthetic",
            "relationship_label": "Child",
            "authority_confirmed": True,
        },
    )
    assert child.status_code == 201
    child_id = child.json()["id"]
    child_headers = {**ORIGIN, "X-Patient-Profile": child_id}
    child_doc = client.post(
        "/api/documents",
        headers=child_headers,
        files={"file": ("history.pdf", PDF, "application/pdf")},
    )
    assert child_doc.status_code == 201
    share = client.post(
        "/api/emergency/shares",
        headers=child_headers,
        json={"fields": ["full_name"], "expires_in_hours": 4, "consent": True},
    )
    assert share.status_code == 201

    with TestClient(app, headers=ORIGIN) as family:
        assert register(family, "archive-viewer@example.com", "Viewer").status_code == 201
        assert (
            client.post(
                f"/api/profiles/{child_id}/access",
                headers=ORIGIN,
                json={"email": "archive-viewer@example.com", "role": "viewer"},
            ).status_code
            == 201
        )

    assert client.delete(f"/api/profiles/{primary_id}", headers=ORIGIN).status_code == 404
    assert client.delete(f"/api/profiles/{child_id}", headers=ORIGIN).status_code == 204
    assert client.get("/api/profiles").json() == [
        {"id": primary_id, "full_name": "Owner", "is_primary": True, "role": "owner"}
    ]
    assert client.get("/api/documents", headers={"X-Patient-Profile": child_id}).status_code == 404
    # The archive keeps the database history but invalidates bearer links and grants.
    assert (
        client.get(f"/api/public/emergency/{share.json()['url'].rsplit('/', 1)[-1]}").status_code
        == 404
    )
    with TestClient(app, headers=ORIGIN) as family:
        assert (
            family.post(
                "/api/auth/login",
                headers=ORIGIN,
                json={"email": "archive-viewer@example.com", "password": "Safe-demo-passphrase-42"},
            ).status_code
            == 200
        )
        assert (
            family.get("/api/profile", headers={"X-Patient-Profile": child_id}).status_code == 404
        )
