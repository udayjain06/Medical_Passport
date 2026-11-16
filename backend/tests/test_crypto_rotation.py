import json
from uuid import UUID

import pytest
from app.config import settings
from app.crypto_storage import ENCRYPTED_PREFIX
from app.document_storage import read as read_document
from app.encrypted_types import EncryptedJSON, EncryptedText
from app.models import DocumentExtraction, MedicalDocument, PatientProfile
from app.rotate_keys import rotate_data
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select, text

from test_phase1 import ORIGIN, register

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF"


def test_encrypted_types_still_read_legacy_plaintext():
    assert EncryptedText().process_result_value("legacy OCR", None) == "legacy OCR"
    assert EncryptedJSON().process_result_value(
        [{"field": "diagnosis", "value": "Legacy diagnosis"}], None
    ) == [{"field": "diagnosis", "value": "Legacy diagnosis"}]


def test_ocr_candidates_and_document_blobs_rotate_to_the_primary_key(client, monkeypatch):
    old_key = Fernet.generate_key().decode()
    new_key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "document_encryption_key", old_key)
    monkeypatch.setattr(settings, "document_encryption_keys", [])
    assert register(client, "rotation@example.com").status_code == 201
    upload = client.post(
        "/api/documents",
        headers=ORIGIN,
        files={"file": ("rotation.pdf", PDF, "application/pdf")},
    )
    assert upload.status_code == 201
    document_id = UUID(upload.json()["id"])

    with client.app.state.test_sessions() as db:
        document = db.get(MedicalDocument, document_id)
        profile = db.get(PatientProfile, document.profile_id)
        extraction = DocumentExtraction(
            document_id=document.id,
            profile_id=profile.id,
            status="needs_review",
            ocr_text="Private synthetic OCR phrase",
            candidates=[{"field": "diagnosis", "value": "Private synthetic candidate"}],
            engine_version="test-rules",
        )
        db.add(extraction)
        db.commit()
        extraction_id = extraction.id

        raw_ocr, raw_candidates = db.execute(
            text("SELECT ocr_text, candidates FROM document_extractions WHERE id=:id"),
            {"id": extraction_id.hex},
        ).one()
        assert raw_ocr.startswith(ENCRYPTED_PREFIX)
        assert "Private synthetic OCR phrase" not in raw_ocr
        encrypted_candidates = json.loads(raw_candidates)
        assert encrypted_candidates.startswith(ENCRYPTED_PREFIX)
        assert "Private synthetic candidate" not in encrypted_candidates

        monkeypatch.setattr(settings, "document_encryption_key", None)
        monkeypatch.setattr(settings, "document_encryption_keys", [new_key, old_key])
        assert rotate_data(db) == (1, 1)

        raw_ocr, raw_candidates = db.execute(
            text("SELECT ocr_text, candidates FROM document_extractions WHERE id=:id"),
            {"id": extraction_id.hex},
        ).one()
        ocr_ciphertext = raw_ocr[len(ENCRYPTED_PREFIX) :].encode("ascii")
        candidates_ciphertext = json.loads(raw_candidates)[len(ENCRYPTED_PREFIX) :].encode("ascii")
        assert Fernet(new_key.encode()).decrypt(ocr_ciphertext) == b"Private synthetic OCR phrase"
        assert (
            Fernet(new_key.encode()).decrypt(candidates_ciphertext)
            == b'[{"field":"diagnosis","value":"Private synthetic candidate"}]'
        )
        with pytest.raises(InvalidToken):
            Fernet(old_key.encode()).decrypt(ocr_ciphertext)

        monkeypatch.setattr(settings, "document_encryption_keys", [new_key])
        stored = db.scalar(select(DocumentExtraction).where(DocumentExtraction.id == extraction_id))
        assert stored.ocr_text == "Private synthetic OCR phrase"
        assert stored.candidates[0]["value"] == "Private synthetic candidate"
        assert read_document(profile.id, document.id) == PDF
