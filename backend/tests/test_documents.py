import io
from uuid import uuid4

import pytest
from app.config import settings
from app.document_storage import _safe_path
from app.main import app
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from test_phase1 import ORIGIN, register

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF"


@pytest.fixture(autouse=True)
def private_tmp_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "document_storage_path", tmp_path / "private")


def test_document_upload_retrieve_metadata_update_delete_and_ownership(client: TestClient):
    assert register(client, "doc-owner@example.com").status_code == 201
    upload = client.post(
        "/api/documents",
        headers=ORIGIN,
        files={"file": ("lab.pdf", PDF, "application/pdf")},
        data={"category": "Laboratory Report"},
    )
    assert upload.status_code == 201, upload.text
    item = upload.json()
    assert item["sha256_checksum"]
    assert client.get("/api/documents").json()[0]["id"] == item["id"]
    assert client.get(f"/api/documents/{item['id']}/content").content == PDF
    assert (
        client.get(
            "/api/documents", params={"category": "Laboratory Report", "search": "lab"}
        ).json()[0]["id"]
        == item["id"]
    )
    changed = client.patch(
        f"/api/documents/{item['id']}", headers=ORIGIN, json={"category": "Blood Report"}
    )
    assert changed.status_code == 200 and changed.json()["category"] == "Blood Report"

    with TestClient(app, headers=ORIGIN) as other:
        assert register(other, "doc-other@example.com").status_code == 201
        assert other.get(f"/api/documents/{item['id']}").status_code == 404
        assert other.get(f"/api/documents/{item['id']}/content").status_code == 404
        assert other.get("/api/documents").json() == []

    assert client.delete(f"/api/documents/{item['id']}", headers=ORIGIN).status_code == 204
    assert client.get(f"/api/documents/{item['id']}").status_code == 404


def test_upload_requires_auth_and_rejects_invalid_files(client: TestClient, monkeypatch):
    assert (
        client.post(
            "/api/documents", headers=ORIGIN, files={"file": ("x.pdf", PDF, "application/pdf")}
        ).status_code
        == 401
    )
    register(client, "doc-invalid@example.com")
    assert (
        client.post(
            "/api/documents",
            headers=ORIGIN,
            files={"file": ("x.exe", b"MZ", "application/octet-stream")},
        ).status_code
        == 415
    )
    assert (
        client.post(
            "/api/documents", headers=ORIGIN, files={"file": ("x.pdf", PDF, "image/png")}
        ).status_code
        == 415
    )
    monkeypatch.setattr(settings, "document_max_size_bytes", 1024)
    assert (
        client.post(
            "/api/documents",
            headers=ORIGIN,
            files={"file": ("x.pdf", PDF + b" " * 1100, "application/pdf")},
        ).status_code
        == 413
    )


def test_storage_paths_are_derived_from_uuids_only(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "document_storage_path", tmp_path / "private")
    target = _safe_path(uuid4(), uuid4())
    assert target.is_relative_to((tmp_path / "private").resolve())
    with pytest.raises(ValueError):
        _safe_path("..", "..")


def test_real_local_ocr_requires_patient_confirmation_before_timeline(client: TestClient):
    assert register(client, "ocr@example.com").status_code == 201
    image = Image.new("RGB", (1200, 240), "white")
    ImageDraw.Draw(image).text(
        (30, 70), "Patient name: Synthetic Patient Blood Group O+", fill="black"
    )
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    uploaded = client.post(
        "/api/documents",
        headers=ORIGIN,
        files={"file": ("synthetic.png", stream.getvalue(), "image/png")},
    )
    assert uploaded.status_code == 201
    document_id = uploaded.json()["id"]
    processed = client.post(f"/api/documents/{document_id}/process", headers=ORIGIN)
    assert processed.status_code == 200, processed.text
    assert processed.json()["status"] == "needs_review"
    assert "Synthetic Patient" in processed.json()["ocr_text"]
    confirmed = client.post(f"/api/documents/{document_id}/extraction/confirm", headers=ORIGIN)
    assert confirmed.status_code == 200
    events = client.get("/api/timeline").json()
    assert events and events[0]["source_document_id"] == document_id
    assert events[0]["source_extraction_id"] == processed.json()["id"]
    assert events[0]["source_candidate_id"]
    assert events[0]["source_document_filename"] == "synthetic.png"
    assert events[0]["source_document_checksum"] == uploaded.json()["sha256_checksum"]
    assert events[0]["verification_status"] == "confirmed"
    assert client.delete(f"/api/documents/{document_id}", headers=ORIGIN).status_code == 204
    retained = client.get("/api/timeline").json()[0]
    assert retained["source_document_id"] is None
    assert retained["source_extraction_id"] is None
    assert retained["source_candidate_id"]
    assert retained["source_document_filename"] == "synthetic.png"
    assert retained["source_document_checksum"] == uploaded.json()["sha256_checksum"]
