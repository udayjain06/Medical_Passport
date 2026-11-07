import io
from datetime import date, timedelta

import pytest
from app.config import Settings
from app.main import app
from fastapi.testclient import TestClient
from PIL import Image

from test_phase1 import ORIGIN, register

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF"
TODAY = date.today()


def _lines(*texts):
    return [{"page": 1, "lines": [{"text": t, "confidence": 0.95} for t in texts]}]


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), "white").save(buf, format="PNG")
    return buf.getvalue()


def _upload_and_process(client, monkeypatch, texts, name="rx.png"):
    import app.routers.extraction as extraction

    monkeypatch.setattr(extraction, "extract_pages", lambda data, fmt: _lines(*texts))
    uploaded = client.post(
        "/api/documents", headers=ORIGIN, files={"file": (name, _png(), "image/png")}
    )
    assert uploaded.status_code == 201, uploaded.text
    doc_id = uploaded.json()["id"]
    processed = client.post(f"/api/documents/{doc_id}/process", headers=ORIGIN)
    assert processed.status_code == 200, processed.text
    return doc_id, processed.json()


RX = [
    "City Care Hospital",
    "Dr. Anil Sharma",
    "Patient Name: Test Patient",
    f"Date: {TODAY.day:02d}/{TODAY.month:02d}/{TODAY.year}",
    "Diagnosis: Type 2 Diabetes Mellitus",
    "Allergy: Penicillin",
    "1. Tab Metformin 500 mg BD x 30 days",
]


def test_rules_extract_structured_facts_and_review_per_item(client: TestClient, monkeypatch):
    assert register(client, "rx@example.com").status_code == 201
    doc_id, data = _upload_and_process(client, monkeypatch, RX)
    fields = {c["field"] for c in data["candidates"]}
    assert {"diagnosis", "allergy", "medication", "doctor_name", "hospital_name"} <= fields
    medication = next(c for c in data["candidates"] if c["field"] == "medication")
    assert all(part in medication["normalized_value"] for part in ("500 mg", "BD", "30 days"))
    assert "source_text" not in fields and data["engine_version"].startswith("rules-v1")
    assert data["warnings"] == []
    reviewed = []
    for c in data["candidates"]:
        status = "rejected" if c["field"] == "medication" else "accepted"
        reviewed.append({**c, "review_status": status})
    assert (
        client.put(
            f"/api/documents/{doc_id}/extraction", headers=ORIGIN, json={"candidates": reviewed}
        ).status_code
        == 200
    )
    done = client.post(f"/api/documents/{doc_id}/extraction/confirm", headers=ORIGIN).json()
    assert done["created_events"] == 2  # diagnosis + allergy; medication was rejected
    events = client.get("/api/timeline").json()
    assert {e["category"] for e in events} == {"Diagnosis", "Allergy"}
    assert all("Dr. Anil Sharma" in e["summary"] for e in events)
    # a confirmed extraction cannot be re-processed (would duplicate the timeline)
    assert client.post(f"/api/documents/{doc_id}/process", headers=ORIGIN).status_code == 409


def test_other_persons_document_triggers_warning(client: TestClient, monkeypatch):
    assert register(client, "mismatch@example.com", "Asha Rao").status_code == 201
    doc_id, data = _upload_and_process(client, monkeypatch, ["Patient Name: Ravi Kumar", *RX[4:]])
    assert any("does not match" in w for w in data["warnings"])
    accepted = [{**candidate, "review_status": "accepted"} for candidate in data["candidates"]]
    assert (
        client.put(
            f"/api/documents/{doc_id}/extraction", headers=ORIGIN, json={"candidates": accepted}
        ).status_code
        == 200
    )
    confirmed = client.post(f"/api/documents/{doc_id}/extraction/confirm", headers=ORIGIN).json()
    assert any("does not match" in warning for warning in confirmed["warnings"])


def test_duplicate_facts_across_documents_are_skipped(client: TestClient, monkeypatch):
    assert register(client, "dupe@example.com").status_code == 201
    created = []
    for name in ("a.png", "b.png"):
        doc_id, data = _upload_and_process(client, monkeypatch, RX, name)
        reviewed = [{**c, "review_status": "accepted"} for c in data["candidates"]]
        client.put(
            f"/api/documents/{doc_id}/extraction", headers=ORIGIN, json={"candidates": reviewed}
        )
        created.append(
            client.post(f"/api/documents/{doc_id}/extraction/confirm", headers=ORIGIN).json()
        )
    assert created[0]["created_events"] == 3 and created[1]["created_events"] == 0
    assert created[1]["skipped_duplicates"] == 3


def test_viewer_cannot_process_or_confirm(client: TestClient):
    assert register(client, "own@example.com").status_code == 201
    profile_id = client.get("/api/profile").json()["id"]
    doc = client.post(
        "/api/documents", headers=ORIGIN, files={"file": ("x.png", _png(), "image/png")}
    ).json()
    with TestClient(app, headers=ORIGIN) as viewer:
        assert register(viewer, "view@example.com").status_code == 201
        client.post(
            f"/api/profiles/{profile_id}/access",
            headers=ORIGIN,
            json={"email": "view@example.com", "role": "viewer"},
        )
        h = {**ORIGIN, "X-Patient-Profile": profile_id}
        assert viewer.post(f"/api/documents/{doc['id']}/process", headers=h).status_code == 403
        assert (
            viewer.put(
                f"/api/documents/{doc['id']}/extraction",
                headers=h,
                json={"candidates": []},
            ).status_code
            == 403
        )
        assert (
            viewer.post(f"/api/documents/{doc['id']}/extraction/confirm", headers=h).status_code
            == 403
        )
        assert (
            viewer.post(f"/api/documents/{doc['id']}/extraction/reject", headers=h).status_code
            == 403
        )


def test_emergency_includes_confirmed_document_facts_and_logs_access(
    client: TestClient, monkeypatch
):
    assert register(client, "em@example.com").status_code == 201
    doc_id, data = _upload_and_process(client, monkeypatch, RX)
    reviewed = [{**c, "review_status": "accepted"} for c in data["candidates"]]
    client.put(f"/api/documents/{doc_id}/extraction", headers=ORIGIN, json={"candidates": reviewed})
    client.post(f"/api/documents/{doc_id}/extraction/confirm", headers=ORIGIN)
    share = client.post(
        "/api/emergency/shares",
        headers=ORIGIN,
        json={
            "fields": ["known_allergies", "current_medications"],
            "expires_in_hours": 8760,
            "consent": True,
            "label": "Wallet card",
        },
    ).json()
    token = share["url"].rsplit("/", 1)[-1]
    public = client.get(f"/api/public/emergency/{token}").json()
    assert public["document_allergies"][0]["text"] == "Penicillin"
    assert public["document_medications"][0]["record_date"] == TODAY.isoformat()
    assert "document_conditions" not in public  # field not consented to
    listed = client.get("/api/emergency/shares").json()[0]
    assert listed["access_count"] == 1 and listed["label"] == "Wallet card"
    log = client.get(f"/api/emergency/shares/{share['id']}/access-log").json()
    assert len(log) == 1 and log[0]["ip_prefix"]


def test_old_prescriptions_are_not_listed_as_current_medication(client: TestClient, monkeypatch):
    assert register(client, "old@example.com").status_code == 201
    old = TODAY - timedelta(days=400)
    texts = [f"Date: {old.day:02d}/{old.month:02d}/{old.year}", "Tab Aspirin 75 mg OD"]
    doc_id, data = _upload_and_process(client, monkeypatch, texts)
    reviewed = [{**c, "review_status": "accepted"} for c in data["candidates"]]
    client.put(f"/api/documents/{doc_id}/extraction", headers=ORIGIN, json={"candidates": reviewed})
    client.post(f"/api/documents/{doc_id}/extraction/confirm", headers=ORIGIN)
    share = client.post(
        "/api/emergency/shares",
        headers=ORIGIN,
        json={"fields": ["current_medications"], "expires_in_hours": 24, "consent": True},
    ).json()
    public = client.get(f"/api/public/emergency/{share['url'].rsplit('/', 1)[-1]}").json()
    assert "document_medications" not in public


def test_renew_rotates_link_and_revokes_old(client: TestClient):
    assert register(client, "renew@example.com").status_code == 201
    first = client.post(
        "/api/emergency/shares",
        headers=ORIGIN,
        json={"fields": ["full_name"], "expires_in_hours": 24, "consent": True},
    ).json()
    renewed = client.post(
        f"/api/emergency/shares/{first['id']}/renew",
        headers=ORIGIN,
        json={"expires_in_hours": 720, "consent": True},
    )
    assert renewed.status_code == 201 and renewed.json()["url"] != first["url"]
    assert client.get(f"/api/public/emergency/{first['url'].rsplit('/', 1)[-1]}").status_code == 404
    assert (
        client.get(f"/api/public/emergency/{renewed.json()['url'].rsplit('/', 1)[-1]}").status_code
        == 200
    )
    too_long = client.post(
        "/api/emergency/shares",
        headers=ORIGIN,
        json={"fields": ["full_name"], "expires_in_hours": 87600, "consent": True},
    )
    assert too_long.status_code == 422


def test_rate_limit_uses_forwarded_ip_when_proxy_is_trusted(client: TestClient, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "trusted_proxy_count", 1)
    monkeypatch.setattr(settings, "emergency_access_rate_per_minute", 2)
    for _ in range(2):
        assert (
            client.get(
                "/api/public/emergency/x", headers={"X-Forwarded-For": "1.1.1.1"}
            ).status_code
            == 404
        )
    assert (
        client.get("/api/public/emergency/x", headers={"X-Forwarded-For": "1.1.1.1"}).status_code
        == 429
    )
    # a different real client behind the same proxy is not locked out
    assert (
        client.get("/api/public/emergency/x", headers={"X-Forwarded-For": "2.2.2.2"}).status_code
        == 404
    )


def test_documents_are_encrypted_at_rest(client: TestClient, monkeypatch, tmp_path):
    from app import document_storage
    from app.config import settings
    from cryptography.fernet import Fernet

    monkeypatch.setattr(settings, "document_encryption_key", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "document_storage_path", tmp_path)
    assert register(client, "enc@example.com").status_code == 201
    doc = client.post(
        "/api/documents", headers=ORIGIN, files={"file": ("e.pdf", PDF, "application/pdf")}
    ).json()
    blob = next(tmp_path.rglob("*.blob")).read_bytes()
    assert blob.startswith(b"MPENC1:") and PDF not in blob
    assert client.get(f"/api/documents/{doc['id']}/content").content == PDF
    assert document_storage  # module import sanity


def test_export_and_account_deletion(client: TestClient, monkeypatch, tmp_path):
    from app.config import settings

    monkeypatch.setattr(settings, "document_storage_path", tmp_path / "private_uploads")
    assert register(client, "gone@example.com", "Goodbye Patient").status_code == 201
    profile_id = client.get("/api/profile").json()["id"]
    doc = client.post(
        "/api/documents", headers=ORIGIN, files={"file": ("record.pdf", PDF, "application/pdf")}
    )
    assert doc.status_code == 201
    blob = tmp_path / "private_uploads" / profile_id / f"{doc.json()['id']}.blob"
    assert blob.exists()
    exported_response = client.get("/api/auth/export")
    exported = exported_response.json()
    assert exported["account"]["email"] == "gone@example.com"
    assert exported["profiles"][0]["full_name"] == "Goodbye Patient"
    assert exported["documents"][0]["filename"] == "record.pdf"
    assert "PDF" not in exported_response.text
    wrong = client.post("/api/auth/delete-account", headers=ORIGIN, json={"password": "nope"})
    assert wrong.status_code == 403 and blob.exists()
    ok = client.post(
        "/api/auth/delete-account", headers=ORIGIN, json={"password": "Safe-demo-passphrase-42"}
    )
    assert ok.status_code == 200 and not blob.exists()
    login = client.post(
        "/api/auth/login",
        headers=ORIGIN,
        json={"email": "gone@example.com", "password": "Safe-demo-passphrase-42"},
    )
    assert login.status_code == 401


def test_production_settings_require_encryption_and_https():
    base = dict(
        app_env="production",
        secret_key="x" * 40,
        database_url="postgresql+psycopg://u:p@h/db",
        cookie_secure=True,
        cors_origins=["https://app.example.com"],
        public_app_url="https://app.example.com",
    )
    with pytest.raises(ValueError):
        Settings(**base)  # no document_encryption_key
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    base_without_secret = {name: value for name, value in base.items() if name != "secret_key"}
    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings(**base_without_secret, document_encryption_key=key)
    with pytest.raises(ValueError):
        Settings(**base, document_encryption_key="not-a-key")
    with pytest.raises(ValueError):
        base_http = {**base, "cors_origins": ["http://localhost:3000"]}
        Settings(**base_http, document_encryption_key=key)
    assert Settings(**base, document_encryption_key=key).app_env == "production"


def test_rules_parse_indian_dates_and_ignore_none_allergies():
    from app.structured_extraction import extract_structured

    candidates = extract_structured(
        _lines(
            "Allergy: NKDA",
            "Allergies: none",
            "Date: 15/07/2024",
            "Admission date: 16-Jul-2024",
            "Discharge date: 2024-07-18",
        )
    )
    assert not any(item["field"] == "allergy" for item in candidates)
    assert {item["field"]: item["value"] for item in candidates} == {
        "document_date": "2024-07-15",
        "admission_date": "2024-07-16",
        "discharge_date": "2024-07-18",
    }


def test_ai_drops_malformed_items_without_losing_valid_candidates(monkeypatch):
    import json

    import app.medical_ai as medical_ai
    from app.config import settings

    monkeypatch.setattr(settings, "medical_ai_endpoint", "https://provider.invalid")
    monkeypatch.setattr(settings, "medical_ai_api_key", "test-key")
    monkeypatch.setattr(settings, "medical_ai_model", "test-model")

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            content = json.dumps(
                {
                    "candidates": [
                        {"field": "unsupported", "value": "bad", "confidence": 0.9},
                        {"field": "diagnosis", "value": "Asthma", "confidence": 0.9},
                        {"field": "allergy", "value": "bad confidence", "confidence": "oops"},
                        {"field": "allergy", "value": "boolean confidence", "confidence": True},
                    ]
                }
            )
            return json.dumps({"choices": [{"message": {"content": content}}]}).encode()

    monkeypatch.setattr(
        medical_ai.urllib.request, "urlopen", lambda *_args, **_kwargs: FakeResponse()
    )
    candidates, engine = medical_ai.extract_candidates(_lines("Diagnosis: Asthma"))
    assert engine == "test-model"
    assert [item["value"] for item in candidates] == ["Asthma"]


def test_ai_provider_failure_falls_back_to_rules(monkeypatch):
    import app.medical_ai as medical_ai
    from app.config import settings

    monkeypatch.setattr(settings, "medical_ai_endpoint", "https://provider.invalid")
    monkeypatch.setattr(settings, "medical_ai_api_key", "test-key")
    monkeypatch.setattr(settings, "medical_ai_model", "test-model")

    def fail(*_args, **_kwargs):
        raise TimeoutError("synthetic provider outage")

    monkeypatch.setattr(medical_ai.urllib.request, "urlopen", fail)
    candidates, engine = medical_ai.extract_candidates(_lines("Diagnosis: Asthma"))
    assert engine == "rules-v1 (ai-fallback)"
    assert candidates[0]["field"] == "diagnosis"


def test_rules_fall_back_to_source_lines_when_no_event_candidates_exist():
    from app.structured_extraction import extract_structured

    candidates = extract_structured(_lines("Patient Name: Meera Rao", "Unknown hospital form"))
    assert [candidate["field"] for candidate in candidates] == [
        "patient_name",
        "hospital_name",
        "source_text",
        "source_text",
    ]
