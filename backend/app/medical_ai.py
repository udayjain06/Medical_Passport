from __future__ import annotations

import json
import urllib.request

from pydantic import BaseModel, Field, field_validator

from app.config import settings

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
        # OCR output stays a human-reviewed source snippet; no clinical facts are inferred.
        raw = [
            {
                "field": "source_text",
                "value": "\n".join(line["text"] for page in pages for line in page["lines"]),
                "source_page": page["page"],
                "original_value": line["text"],
                "normalized_value": None,
                "confidence": line["confidence"],
                "review_status": "pending",
            }
            for page in pages
            for line in page["lines"]
        ]
        return [CandidateFact.model_validate(item).model_dump() for item in raw], "ocr-only"
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
        clean.append(
            CandidateFact.model_validate({**item, "review_status": "pending"}).model_dump()
        )
    return clean, settings.medical_ai_model
