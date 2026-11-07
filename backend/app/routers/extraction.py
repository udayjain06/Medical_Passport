from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import document_storage
from app.database import get_db
from app.dependencies import get_current_user
from app.extraction import extract_pages
from app.medical_ai import ALLOWED_FIELDS, extract_candidates
from app.models import (
    AuditEvent,
    DocumentExtraction,
    MedicalDocument,
    PatientProfile,
    TimelineEvent,
    User,
)
from app.profile_access import require_write
from app.routers.documents import _document
from app.structured_extraction import names_match

router = APIRouter(prefix="/api/documents", tags=["document extraction"])


class ReviewPayload(BaseModel):
    candidates: list[dict] = Field(max_length=300)


REVIEW_STATUSES = {"pending", "accepted", "rejected"}
# How each reviewed field becomes a timeline event: (category, title prefix).
TIMELINE_MAP = {
    "diagnosis": ("Diagnosis", "Diagnosis"),
    "condition": ("Diagnosis", "Condition"),
    "allergy": ("Allergy", "Allergy"),
    "medication": ("Prescription", "Medication"),
    "procedure": ("Surgery", "Procedure"),
    "lab_test": ("Lab test", "Lab"),
    "admission_date": ("Admission", "Admission"),
    "discharge_date": ("Discharge", "Discharge"),
    "follow_up_date": ("Follow-up", "Follow-up"),
    "source_text": ("Medical observation", "Source text"),
}
DATE_EVENT_FIELDS = {"admission_date", "discharge_date", "follow_up_date"}


def _serialize(extraction: DocumentExtraction, db: Session | None = None, **extra) -> dict:
    data = {
        "id": str(extraction.id),
        "document_id": str(extraction.document_id),
        "status": extraction.status,
        "ocr_text": extraction.ocr_text,
        "candidates": extraction.candidates,
        "engine_version": extraction.engine_version,
        "created_at": extraction.created_at,
        "updated_at": extraction.updated_at,
        "warnings": [],
    }
    data.update(extra)
    return data


def _warnings(db: Session, profile_id: uuid.UUID, candidates: list[dict]) -> list[str]:
    profile = db.get(PatientProfile, profile_id)
    warnings: list[str] = []
    for item in candidates:
        if item.get("field") == "patient_name" and profile and profile.full_name:
            if not names_match(item["value"], profile.full_name):
                warnings.append(
                    f"This document names '{item['value']}', which does not match this "
                    f"profile ('{profile.full_name}'). Check it belongs to the right person "
                    "before accepting."
                )
    return warnings


def _role(db: Session, user: User, doc: MedicalDocument, header: uuid.UUID | None) -> str:
    from app.profile_access import resolve_profile

    return resolve_profile(db, user, doc.profile_id)[1]


def _get_extraction(db: Session, doc: MedicalDocument) -> DocumentExtraction:
    extraction = db.scalar(
        select(DocumentExtraction).where(
            DocumentExtraction.document_id == doc.id,
            DocumentExtraction.profile_id == doc.profile_id,
        )
    )
    if extraction is None:
        raise HTTPException(404, "No extraction exists for this document")
    return extraction


@router.post("/{document_id}/process")
def process_document(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_patient_profile: uuid.UUID | None = Header(None),
):
    doc = _document(db, user, document_id, x_patient_profile)
    require_write(_role(db, user, doc, x_patient_profile))
    extraction = db.scalar(
        select(DocumentExtraction).where(DocumentExtraction.document_id == doc.id)
    )
    if extraction is not None and extraction.status == "confirmed":
        raise HTTPException(
            409,
            "This document is already confirmed. Delete its timeline entries before re-processing.",
        )
    if extraction is None:
        extraction = DocumentExtraction(
            document_id=doc.id,
            profile_id=doc.profile_id,
            status="processing",
            engine_version="rapidocr+rules-v1",
        )
        db.add(extraction)
    else:
        extraction.status = "processing"
        extraction.updated_at = datetime.now(UTC)
    doc.processing_status = "processing"
    db.commit()
    try:
        pages = extract_pages(document_storage.read(doc.profile_id, doc.id), doc.file_format)
        candidates, engine = extract_candidates(pages)
        extraction.candidates = [
            {**candidate, "candidate_id": candidate.get("candidate_id") or str(uuid.uuid4())}
            for candidate in candidates
        ]
        extraction.ocr_text = "\n".join(line["text"] for page in pages for line in page["lines"])
        extraction.engine_version = engine
        extraction.status = "needs_review"
        doc.processing_status = extraction.status
        db.commit()
    except Exception:
        extraction.status = "failed"
        doc.processing_status = "failed"
        db.commit()
        raise HTTPException(503, "Document processing failed; you can retry") from None
    return _serialize(extraction, warnings=_warnings(db, doc.profile_id, extraction.candidates))


@router.get("/{document_id}/extraction")
def read_extraction(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_patient_profile: uuid.UUID | None = Header(None),
):
    doc = _document(db, user, document_id, x_patient_profile)
    extraction = _get_extraction(db, doc)
    return _serialize(extraction, warnings=_warnings(db, doc.profile_id, extraction.candidates))


@router.put("/{document_id}/extraction")
def update_extraction(
    document_id: uuid.UUID,
    payload: ReviewPayload,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_patient_profile: uuid.UUID | None = Header(None),
):
    doc = _document(db, user, document_id, x_patient_profile)
    require_write(_role(db, user, doc, x_patient_profile))
    extraction = _get_extraction(db, doc)
    if extraction.status in {"confirmed", "rejected"}:
        raise HTTPException(409, "This extraction is closed and can no longer be edited")
    clean = []
    for item in payload.candidates:
        if not isinstance(item.get("field"), str) or not isinstance(item.get("value"), str):
            raise HTTPException(422, "Each candidate needs a field and text value")
        confidence = item.get("confidence", 0)
        if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            raise HTTPException(422, "Candidate confidence must be between zero and one")
        if item["field"] not in TIMELINE_MAP and item["field"] not in ALLOWED_FIELDS:
            raise HTTPException(422, "Unsupported candidate field")
        value = item["value"].strip()
        if not value or len(value) > 2000:
            raise HTTPException(422, "Candidate text must be 1 to 2000 characters")
        status = item.get("review_status", "pending")
        if not isinstance(status, str) or status not in REVIEW_STATUSES:
            raise HTTPException(422, "Review status must be pending, accepted or rejected")
        clean.append(
            {
                **item,
                "value": value,
                "candidate_id": item.get("candidate_id") or str(uuid.uuid4()),
                "review_status": status,
            }
        )
    extraction.candidates = clean
    extraction.updated_at = datetime.now(UTC)
    extraction.status = "needs_review"
    doc.processing_status = extraction.status
    db.commit()
    return _serialize(extraction, warnings=_warnings(db, doc.profile_id, extraction.candidates))


@router.post("/{document_id}/extraction/confirm")
def confirm_extraction(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_patient_profile: uuid.UUID | None = Header(None),
):
    doc = _document(db, user, document_id, x_patient_profile)
    require_write(_role(db, user, doc, x_patient_profile))
    extraction = _get_extraction(db, doc)
    if extraction.status != "needs_review":
        raise HTTPException(409, "Only reviewed candidates can be confirmed")
    candidates = [dict(c) for c in extraction.candidates]
    accepted = [c for c in candidates if c.get("review_status") == "accepted"]
    if not accepted:
        raise HTTPException(422, "Accept at least one item before confirming")
    doctor = next((c["value"] for c in accepted if c["field"] == "doctor_name"), None)
    hospital = next((c["value"] for c in accepted if c["field"] == "hospital_name"), None)
    document_date = doc.document_date
    for c in accepted:
        if c["field"] == "document_date":
            try:
                document_date = date.fromisoformat(c.get("normalized_value") or c["value"])
            except ValueError:
                pass
    source = ", ".join(part for part in (doctor, hospital) if part)
    created = skipped = 0
    for candidate in candidates:
        if candidate.get("review_status") != "accepted":
            continue
        field = candidate["field"]
        if field not in TIMELINE_MAP:
            candidate["review_status"] = "confirmed"  # context-only facts: doctor, hospital, date
            continue
        candidate_id = candidate.get("candidate_id") or str(uuid.uuid4())
        candidate["candidate_id"] = candidate_id
        category, prefix = TIMELINE_MAP[field]
        event_date = document_date
        if field in DATE_EVENT_FIELDS:
            try:
                event_date = date.fromisoformat(
                    candidate.get("normalized_value") or candidate["value"]
                )
            except ValueError:
                event_date = document_date
        title = f"{prefix}: {candidate['value']}"[:200]
        summary = candidate["value"] if not source else f"{candidate['value']} — {source}"
        duplicate = db.scalar(
            select(TimelineEvent.id).where(
                TimelineEvent.profile_id == doc.profile_id,
                TimelineEvent.category == category,
                TimelineEvent.title == title,
                TimelineEvent.event_date == event_date,
            )
        )
        if duplicate:
            candidate["review_status"] = "duplicate_skipped"
            skipped += 1
            continue
        candidate["review_status"] = "confirmed"
        db.add(
            TimelineEvent(
                profile_id=doc.profile_id,
                source_document_id=doc.id,
                source_extraction_id=extraction.id,
                source_candidate_id=candidate_id,
                source_document_filename=doc.original_filename,
                source_document_checksum=doc.sha256_checksum,
                title=title,
                category=category,
                event_date=event_date,
                summary=summary[:5000],
                source_page=candidate.get("source_page"),
                provenance="patient_confirmed",
                verification_status="confirmed",
            )
        )
        created += 1
    extraction.candidates = candidates
    extraction.status = "confirmed"
    extraction.updated_at = datetime.now(UTC)
    doc.processing_status = "confirmed"
    db.add(
        AuditEvent(
            user_id=user.id,
            action="document.extraction_confirmed",
            target_type="medical_document",
            target_id=doc.id,
        )
    )
    db.commit()
    return _serialize(
        extraction,
        created_events=created,
        skipped_duplicates=skipped,
        warnings=_warnings(db, doc.profile_id, candidates),
    )


@router.post("/{document_id}/extraction/reject")
def reject_extraction(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_patient_profile: uuid.UUID | None = Header(None),
):
    doc = _document(db, user, document_id, x_patient_profile)
    require_write(_role(db, user, doc, x_patient_profile))
    extraction = _get_extraction(db, doc)
    if extraction.status in {"confirmed", "rejected"}:
        raise HTTPException(409, "This extraction is closed and can no longer be changed")
    extraction.status = "rejected"
    extraction.updated_at = datetime.now(UTC)
    doc.processing_status = "rejected"
    db.add(
        AuditEvent(
            user_id=user.id,
            action="document.extraction_rejected",
            target_type="medical_document",
            target_id=doc.id,
        )
    )
    db.commit()
    return _serialize(extraction, warnings=_warnings(db, doc.profile_id, extraction.candidates))
