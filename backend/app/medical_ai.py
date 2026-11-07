from __future__ import annotations

import json
import urllib.request

from pydantic import BaseModel, Field, field_validator

from app.config import settings
from app.structured_extraction import extract_structured

ALLOWED_FIELDS = {
    "source_text",
    "patient_name",
    "document_date",
    "doctor_name",
    "hospital_name",
    "diagnosis",
    "condition",
    "allergy",
    "medication",
    "dosage",
    "frequency",
    "duration",
    "procedure",
    "admission_date",
    "discharge_date",
    "follow_up_date",
    "lab_test",
    "result_value",
    "unit",
    "reference_range",
    "abnormal_indicator",
}


class CandidateFact(BaseModel):
    field: str = Field(min_length=1, max_length=40)
    value: str = Field(min_length=1, max_length=2000)
    source_page: int | None = Field(default=None, ge=1)
    original_value: str | None = Field(default=None, max_length=2000)
    normalized_value: str | None = Field(default=None, max_length=2000)
    confidence: float = Field(ge=0, le=1)
    review_status: str = "pending"

    @field_validator("review_status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in {"pending", "accepted", "rejected"}:
            raise ValueError("Unsupported review status")
        return value

    @field_validator("field")
    @classmethod
    def validate_field(cls, value: str) -> str:
        if value not in ALLOWED_FIELDS:
            raise ValueError("Unsupported candidate field")
        return value


def extract_candidates(pages: list[dict]) -> tuple[list[dict], str]:
    if not (
        settings.medical_ai_endpoint and settings.medical_ai_api_key and settings.medical_ai_model
    ):
        return _rules(pages), "rules-v1"
    prompt = {
        "model": settings.medical_ai_model,
        "temperature": 0,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Extract only explicitly stated medical facts. Do not diagnose, infer, or add "
                    "missing details. Return JSON {candidates:[{field,value,source_page,"
                    "original_value,normalized_value,confidence}]}. Confidence is 0..1."
                ),
            },
            {"role": "user", "content": json.dumps(pages, ensure_ascii=False)},
        ],
        "response_format": {"type": "json_object"},
    }
    try:
        return _ai_candidates(prompt), settings.medical_ai_model
    except Exception:  # provider outage or malformed output: fall back to offline rules
        return _rules(pages), "rules-v1 (ai-fallback)"


def _rules(pages: list[dict]) -> list[dict]:
    return [CandidateFact.model_validate(c).model_dump() for c in extract_structured(pages)]


def _ai_candidates(prompt: dict) -> list[dict]:
    request = urllib.request.Request(
        settings.medical_ai_endpoint,
        data=json.dumps(prompt).encode(),
        headers={
            "Authorization": f"Bearer {settings.medical_ai_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read())
    content = payload["choices"][0]["message"]["content"]
    decoded = json.loads(content)
    values = decoded.get("candidates", [])
    if not isinstance(values, list):
        raise ValueError("AI response did not contain a candidate list")
    clean = []
    for item in values:
        if not isinstance(item, dict) or not isinstance(item.get("value"), str):
            continue
        confidence = float(item.get("confidence", 0))
        if not 0 <= confidence <= 1:
            continue
        try:
            clean.append(
                CandidateFact.model_validate({**item, "review_status": "pending"}).model_dump()
            )
        except ValueError:
            continue  # drop one malformed or unsupported item instead of the whole run
    if not clean:
        raise ValueError("AI response contained no usable candidates")
    return clean
