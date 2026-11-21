from __future__ import annotations

import json
import re
import urllib.request
from copy import deepcopy

from pydantic import BaseModel, Field, field_validator

from app.config import settings
from app.structured_extraction import extract_structured

ALLOWED_FIELDS = {
    "source_text",
    "patient_name",
    "age",
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

_NUMBER_LIKE = re.compile(r"(?<!\d)\+?(?:\d[ \t().-]*){9,}\d(?!\d)")


def provider_configured() -> bool:
    return bool(
        settings.medical_ai_endpoint and settings.medical_ai_api_key and settings.medical_ai_model
    )


def redact_for_provider(pages: list[dict], patient_name: str | None) -> list[dict]:
    """Return sanitized OCR page data without changing the local source text."""
    safe_pages = deepcopy(pages)
    name_pattern = None
    if patient_name and patient_name.strip():
        pattern = re.escape(patient_name.strip())
        pattern = re.sub(r"\\\s+", r"\\s+", pattern)
        name_pattern = re.compile(rf"(?<!\w){pattern}(?!\w)", re.IGNORECASE)

    def redact_text(value: str) -> str:
        if name_pattern:
            value = name_pattern.sub("[REDACTED NAME]", value)

        def redact_number(match: re.Match[str]) -> str:
            digits = re.sub(r"\D", "", match.group())
            return "[REDACTED NUMBER]" if len(digits) >= 10 else match.group()

        return _NUMBER_LIKE.sub(redact_number, value)

    for page in safe_pages:
        for line in page.get("lines", []):
            if isinstance(line, dict) and isinstance(line.get("text"), str):
                line["text"] = redact_text(line["text"])
    return safe_pages


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


def extract_candidates(pages: list[dict], allow_ai: bool = True) -> tuple[list[dict], str]:
    if not allow_ai or not provider_configured():
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
        try:
            raw_confidence = item.get("confidence", 0)
            if isinstance(raw_confidence, bool):
                continue
            confidence = float(raw_confidence)
            if not 0 <= confidence <= 1:
                continue
            clean.append(
                CandidateFact.model_validate({**item, "review_status": "pending"}).model_dump()
            )
        except (TypeError, ValueError, OverflowError):
            continue  # drop one malformed or unsupported item instead of the whole run
    if not clean:
        raise ValueError("AI response contained no usable candidates")
    return clean
