import json
from uuid import UUID

from app.config import settings
from app.models import DocumentExtraction
from sqlalchemy import select

from test_phase1 import ORIGIN, register
from test_production_hardening import PDF, _lines


def _enable_provider(monkeypatch):
    monkeypatch.setattr(settings, "medical_ai_endpoint", "https://provider.invalid/v1/chat")
    monkeypatch.setattr(settings, "medical_ai_api_key", "synthetic-test-key")
    monkeypatch.setattr(settings, "medical_ai_model", "synthetic-provider-model")


def test_configured_provider_is_never_called_without_per_run_consent(client, monkeypatch):
    import app.medical_ai as medical_ai
    import app.routers.extraction as extraction

    assert register(client, "no-ai-consent@example.com").status_code == 201
    _enable_provider(monkeypatch)
    monkeypatch.setattr(extraction, "extract_pages", lambda *_args: _lines("Diagnosis: Asthma"))
    provider_calls = []
    monkeypatch.setattr(medical_ai, "_ai_candidates", lambda prompt: provider_calls.append(prompt))

    upload = client.post(
        "/api/documents", headers=ORIGIN, files={"file": ("ai.png", PDF, "application/pdf")}
    )
    assert upload.status_code == 201
    document_id = upload.json()["id"]
    response = client.post(f"/api/documents/{document_id}/process", headers=ORIGIN)

    assert response.status_code == 200, response.text
    assert provider_calls == []
    assert response.json()["engine_version"] == "rules-v1"
    assert response.json()["ai_consent"] is False
    assert response.json()["ai_provider"] is None


def test_explicit_ai_consent_sends_redacted_ocr_and_records_provider(client, monkeypatch):
    import app.medical_ai as medical_ai
    import app.routers.extraction as extraction

    assert register(client, "ai-consent@example.com", "Asha Rao").status_code == 201
    _enable_provider(monkeypatch)
    monkeypatch.setattr(
        extraction,
        "extract_pages",
        lambda *_args: _lines("Patient name: Asha Rao", "Phone: 9876543210", "Diagnosis: Asthma"),
    )
    sent_prompts = []

    def fake_provider(prompt):
        sent_prompts.append(prompt)
        return [
            {
                "field": "diagnosis",
                "value": "Asthma",
                "source_page": 1,
                "confidence": 0.91,
            }
        ]

    monkeypatch.setattr(medical_ai, "_ai_candidates", fake_provider)
    upload = client.post(
        "/api/documents", headers=ORIGIN, files={"file": ("ai.png", PDF, "application/pdf")}
    )
    assert upload.status_code == 201
    document_id = upload.json()["id"]
    response = client.post(
        f"/api/documents/{document_id}/process",
        headers=ORIGIN,
        json={"ai_consent": True},
    )

    assert response.status_code == 200, response.text
    prompt_text = sent_prompts[0]["messages"][1]["content"]
    assert "Asha Rao" not in prompt_text
    assert "9876543210" not in prompt_text
    assert "[REDACTED NAME]" in prompt_text
    assert "[REDACTED NUMBER]" in prompt_text
    assert (
        response.json()["ocr_text"]
        == "Patient name: Asha Rao\nPhone: 9876543210\nDiagnosis: Asthma"
    )
    assert response.json()["ai_consent"] is True
    assert response.json()["ai_provider"] == "synthetic-provider-model"
    assert response.json()["ai_processed_at"]

    with client.app.state.test_sessions() as db:
        saved = db.scalar(
            select(DocumentExtraction).where(
                DocumentExtraction.document_id == UUID(upload.json()["id"])
            )
        )
        assert saved is not None and saved.ai_consent is True
        assert saved.ai_provider == "synthetic-provider-model"
        assert saved.ai_processed_at is not None


def test_ai_capability_endpoint_does_not_disclose_provider_secrets(client, monkeypatch):
    assert register(client, "ai-capabilities@example.com").status_code == 201
    _enable_provider(monkeypatch)
    response = client.get("/api/auth/ai-capabilities")

    assert response.status_code == 200
    assert response.json() == {"external_ai_configured": True}
    assert "synthetic-test-key" not in json.dumps(response.json())
