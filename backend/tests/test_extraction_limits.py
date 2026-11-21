import io

import pytest
from app.config import settings
from PIL import Image

from test_phase1 import ORIGIN, register


def test_oversized_image_is_rejected_clearly(monkeypatch):
    import app.extraction as extraction

    buffer = io.BytesIO()
    Image.new("RGB", (20, 20), "white").save(buffer, format="PNG")
    monkeypatch.setattr(extraction.Image, "MAX_IMAGE_PIXELS", 100)
    with pytest.raises(extraction.OversizedImage, match="too large"):
        extraction.extract_pages(buffer.getvalue(), "png")


def test_oversized_image_returns_422(client, monkeypatch):
    import app.extraction as extraction

    buffer = io.BytesIO()
    Image.new("RGB", (20, 20), "white").save(buffer, format="PNG")
    monkeypatch.setattr(extraction.Image, "MAX_IMAGE_PIXELS", 100)
    assert register(client, "large-image@example.com").status_code == 201
    uploaded = client.post(
        "/api/documents",
        headers=ORIGIN,
        files={"file": ("large.png", buffer.getvalue(), "image/png")},
    )
    assert uploaded.status_code == 201
    response = client.post(f"/api/documents/{uploaded.json()['id']}/process", headers=ORIGIN)
    assert response.status_code == 422
    assert response.json()["detail"] == "Image is too large to process safely"


def test_document_processing_is_rate_limited_per_user(client, monkeypatch):
    import app.routers.extraction as extraction_router

    monkeypatch.setattr(settings, "document_process_rate_limit_count", 1)
    monkeypatch.setattr(extraction_router, "extract_pages", lambda _data, _fmt: [])
    buffer = io.BytesIO()
    Image.new("RGB", (10, 10), "white").save(buffer, format="PNG")
    assert register(client, "process-limit@example.com").status_code == 201
    uploaded = client.post(
        "/api/documents",
        headers=ORIGIN,
        files={"file": ("small.png", buffer.getvalue(), "image/png")},
    )
    assert uploaded.status_code == 201
    path = f"/api/documents/{uploaded.json()['id']}/process"
    assert client.post(path, headers=ORIGIN).status_code == 200
    limited = client.post(path, headers=ORIGIN)
    assert limited.status_code == 429
