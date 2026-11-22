from __future__ import annotations

import hashlib
from urllib.parse import urlsplit
from uuid import UUID

from app import document_storage
from app.config import settings
from app.demo_fixtures import DEMO_DOCUMENTS, DEMO_EMAIL, fixture_bytes
from app.demo_seed import seed_demo
from app.models import (
    AuditEvent,
    ConsentRecord,
    DocumentExtraction,
    EmergencyAccessLog,
    EmergencyShare,
    MedicalDocument,
    PatientProfile,
    ProfileAccess,
    TimelineEvent,
    User,
)
from app.routers import extraction as extraction_router
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from test_phase1 import ORIGIN, register


def _seed(client: TestClient, monkeypatch) -> dict[str, int]:
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "demo_mode", True)
    with client.app.state.test_sessions() as db:
        return seed_demo(db)


def test_demo_login_is_disabled_by_default_and_in_production(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "demo_mode", False)
    monkeypatch.setattr(settings, "app_env", "development")
    assert client.get("/api/auth/demo-status").json() == {"enabled": False}
    assert client.post("/api/auth/demo-login", headers=ORIGIN).status_code == 404

    monkeypatch.setattr(settings, "demo_mode", True)
    monkeypatch.setattr(settings, "app_env", "production")
    assert client.get("/api/auth/demo-status").json() == {"enabled": False}
    assert client.post("/api/auth/demo-login", headers=ORIGIN).status_code == 404


def test_demo_seed_is_idempotent_and_preserves_normal_users(client: TestClient, monkeypatch):
    ordinary = register(client, "ordinary-demo-test@example.com", "Existing Patient")
    assert ordinary.status_code == 201
    ordinary_id = UUID(ordinary.json()["user"]["id"])

    first = _seed(client, monkeypatch)
    second = _seed(client, monkeypatch)
    assert first == {
        "created_user": 1,
        "created_primary_profile": 1,
        "created_dependent_profile": 1,
        "documents_present": 5,
        "created_emergency_share": 1,
    }
    assert second == {
        "created_user": 0,
        "created_primary_profile": 0,
        "created_dependent_profile": 0,
        "documents_present": 5,
        "created_emergency_share": 0,
    }

    with client.app.state.test_sessions() as db:
        ordinary_user = db.get(User, ordinary_id)
        demo_user = db.scalar(select(User).where(User.email == DEMO_EMAIL))
        assert ordinary_user is not None
        assert ordinary_user.is_demo is False
        assert ordinary_user.profiles[0].full_name == "Existing Patient"
        assert demo_user is not None and demo_user.is_demo
        assert demo_user.email_verified_at is not None

        primary = db.scalar(
            select(PatientProfile).where(
                PatientProfile.user_id == demo_user.id,
                PatientProfile.is_primary.is_(True),
            )
        )
        assert primary is not None
        assert primary.full_name == "Aarav Mehta"
        assert str(primary.date_of_birth) == "2001-08-14"
        assert primary.blood_group == "O+"
        assert "Pollen" in primary.known_allergies
        assert "Seasonal allergic rhinitis" in primary.major_conditions
        assert "Cetirizine 10 mg" in primary.current_medications
        assert any(contact.full_name == "Riya Mehta" for contact in primary.emergency_contacts)

        docs = db.scalars(
            select(MedicalDocument).where(MedicalDocument.profile_id == primary.id)
        ).all()
        assert {doc.original_filename for doc in docs} == {
            fixture.filename for fixture in DEMO_DOCUMENTS
        }
        for doc in docs:
            stored = document_storage.read(doc.profile_id, doc.id)
            assert stored.startswith(b"%PDF-1.4")
            assert "SYNTHETIC TEST DOCUMENT — NOT FOR CLINICAL USE".encode("cp1252") in stored
            assert hashlib.sha256(stored).hexdigest() == doc.sha256_checksum

        extraction = db.scalar(
            select(DocumentExtraction)
            .join(MedicalDocument)
            .where(
                MedicalDocument.profile_id == primary.id,
                MedicalDocument.original_filename == "demo-historical-prescription.pdf",
            )
        )
        assert extraction is not None
        assert extraction.status == "needs_review"
        assert extraction.engine_version.startswith("DEMO EXTRACTION SIMULATION")
        assert any(
            candidate["field"] == "medication" and candidate["review_status"] == "pending"
            for candidate in extraction.candidates
        )

        events = db.scalars(
            select(TimelineEvent).where(TimelineEvent.profile_id == primary.id)
        ).all()
        reported = next(event for event in events if event.category == "Allergy")
        confirmed = next(event for event in events if event.verification_status == "confirmed")
        assert reported.provenance == "patient_reported"
        assert reported.verification_status == "patient_entered"
        assert confirmed.source_document_id is not None
        assert confirmed.source_extraction_id is not None
        assert confirmed.source_candidate_id

        dependent = db.scalar(
            select(PatientProfile).where(
                PatientProfile.user_id == demo_user.id,
                PatientProfile.is_primary.is_(False),
            )
        )
        assert dependent is not None and dependent.full_name == "Ira Mehta"
        assert db.scalar(
            select(ProfileAccess.id).where(
                ProfileAccess.profile_id == dependent.id,
                ProfileAccess.user_id == demo_user.id,
                ProfileAccess.role == "owner",
            )
        )
        assert {
            item
            for item in db.scalars(
                select(ConsentRecord.purpose).where(ConsentRecord.user_id == demo_user.id)
            )
        } >= {"terms", "privacy", "emergency_sharing"}
        assert (
            db.scalar(
                select(func.count())
                .select_from(EmergencyShare)
                .where(
                    EmergencyShare.profile_id == primary.id,
                    EmergencyShare.revoked_at.is_(None),
                )
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.user_id == demo_user.id)
            )
            > 0
        )


def test_demo_login_uses_only_the_seeded_account_and_sets_http_only_cookie(
    client: TestClient, monkeypatch
):
    _seed(client, monkeypatch)
    response = client.post(
        "/api/auth/demo-login",
        headers=ORIGIN,
        json={"email": "someone-else@example.com", "user_id": "arbitrary"},
    )
    assert response.status_code == 200
    assert response.json()["user"]["email"] == DEMO_EMAIL
    assert response.json()["user"]["is_demo"] is True
    assert "httponly" in response.headers["set-cookie"].lower()
    assert client.get("/api/auth/me").json()["email"] == DEMO_EMAIL
    assert client.get("/api/auth/demo-status").json() == {"enabled": True}


def test_demo_ocr_fallback_is_limited_to_known_demo_fixtures(client: TestClient, monkeypatch):
    _seed(client, monkeypatch)
    monkeypatch.setattr(extraction_router, "provider_configured", lambda: True)
    monkeypatch.setattr(
        extraction_router, "extract_pages", lambda *_args: (_ for _ in ()).throw(RuntimeError())
    )
    assert client.post("/api/auth/demo-login", headers=ORIGIN).status_code == 200
    with client.app.state.test_sessions() as db:
        demo = db.scalar(select(User).where(User.email == DEMO_EMAIL))
        profile = db.scalar(
            select(PatientProfile).where(
                PatientProfile.user_id == demo.id, PatientProfile.is_primary.is_(True)
            )
        )
        cbc = db.scalar(
            select(MedicalDocument).where(
                MedicalDocument.profile_id == profile.id,
                MedicalDocument.original_filename == DEMO_DOCUMENTS[0].filename,
            )
        )
        cbc_id = cbc.id
    response = client.post(
        f"/api/documents/{cbc_id}/process",
        headers=ORIGIN,
        json={"ai_consent": True},
    )
    assert response.status_code == 200
    assert response.json()["demo_simulation"] is True
    assert response.json()["engine_version"].startswith("DEMO EXTRACTION SIMULATION")
    assert response.json()["ai_consent"] is False
    assert all(item["review_status"] == "pending" for item in response.json()["candidates"])
    with client.app.state.test_sessions() as db:
        assert (
            db.scalar(select(TimelineEvent.id).where(TimelineEvent.source_document_id == cbc_id))
            is None
        )

    register(client, "ordinary-ocr@example.com", "Ordinary Patient")
    ordinary_doc = client.post(
        "/api/documents",
        headers=ORIGIN,
        files={"file": ("ordinary-copy.pdf", fixture_bytes(DEMO_DOCUMENTS[0]), "application/pdf")},
    )
    assert ordinary_doc.status_code == 201
    failed = client.post(f"/api/documents/{ordinary_doc.json()['id']}/process", headers=ORIGIN)
    assert failed.status_code == 503


def test_demo_emergency_share_is_public_scoped_and_revocable(client: TestClient, monkeypatch):
    _seed(client, monkeypatch)
    client.post("/api/auth/demo-login", headers=ORIGIN)
    created = client.post(
        "/api/emergency/shares",
        headers=ORIGIN,
        json={
            "fields": ["full_name", "blood_group", "known_allergies"],
            "expires_in_hours": 12,
            "consent": True,
            "label": "E2E demo scan",
        },
    )
    assert created.status_code == 201
    token = urlsplit(created.json()["url"]).path.rsplit("/", 1)[-1]

    with TestClient(client.app) as scanner:
        public = scanner.get(f"/api/public/emergency/{token}")
    assert public.status_code == 200
    data = public.json()
    assert data["demo_data"] is True
    assert data["full_name"] == "Aarav Mehta"
    assert data["blood_group"] == "O+"
    assert "known_allergies" in data
    assert "current_medications" not in data
    assert "emergency_contacts" not in data

    with client.app.state.test_sessions() as db:
        share = db.scalar(
            select(EmergencyShare).where(
                EmergencyShare.token_hash == hashlib.sha256(token.encode()).hexdigest()
            )
        )
        assert share is not None
        share_id = share.id
        assert (
            db.scalar(
                select(func.count())
                .select_from(EmergencyAccessLog)
                .where(EmergencyAccessLog.share_id == share.id)
            )
            == 1
        )
    assert client.delete(f"/api/emergency/shares/{share_id}", headers=ORIGIN).status_code == 204
    with TestClient(client.app) as scanner:
        assert scanner.get(f"/api/public/emergency/{token}").status_code == 404


def test_demo_configuration_is_rejected_in_production():
    import pytest
    from app.config import Settings
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="DEMO_MODE must be false"):
        Settings(
            _env_file=None,
            app_env="production",
            demo_mode=True,
            secret_key="a" * 64,
            cookie_secure=True,
            cors_origins=["https://app.example.invalid"],
            public_app_url="https://app.example.invalid",
            document_encryption_keys=[],
        )
