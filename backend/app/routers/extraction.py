from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import document_storage
from app.database import get_db
from app.dependencies import get_current_user
from app.extraction import extract_pages
from app.medical_ai import extract_candidates
from app.models import (
    AuditEvent,
    DocumentExtraction,
    MedicalDocument,
    TimelineEvent,
    User,
)
from app.routers.documents import _document

router = APIRouter(prefix="/api/documents", tags=["document extraction"])


class ReviewPayload(BaseModel):
    candidates: list[dict] = Field(max_length=300)


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
    extraction = db.scalar(
        select(DocumentExtraction).where(DocumentExtraction.document_id == doc.id)
    )
    if extraction is None:
        extraction = DocumentExtraction(
            document_id=doc.id,
            profile_id=doc.profile_id,
            status="processing",
            engine_version="rapidocr+configurable-openai-compatible",
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
        extraction.status = "needs_review" if candidates else "needs_review"
        doc.processing_status = extraction.status
        db.commit()
    except Exception:
        extraction.status = "failed"
        doc.processing_status = "failed"
        db.commit()
        raise HTTPException(503, "Document processing failed; you can retry") from None
    return extraction


@router.get("/{document_id}/extraction")
def read_extraction(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_patient_profile: uuid.UUID | None = Header(None),
):
    doc = _document(db, user, document_id, x_patient_profile)
    return _get_extraction(db, doc)


@router.put("/{document_id}/extraction")
def update_extraction(
    document_id: uuid.UUID,
    payload: ReviewPayload,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_patient_profile: uuid.UUID | None = Header(None),
):
    doc = _document(db, user, document_id, x_patient_profile)
    extraction = _get_extraction(db, doc)
    clean = []
    for item in payload.candidates:
        if not isinstance(item.get("field"), str) or not isinstance(item.get("value"), str):
            raise HTTPException(422, "Each candidate needs a field and text value")
        confidence = item.get("confidence", 0)
        if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            raise HTTPException(422, "Candidate confidence must be between zero and one")
        clean.append(
            {
                **item,
                "candidate_id": item.get("candidate_id") or str(uuid.uuid4()),
                "review_status": "pending",
            }
        )
    extraction.candidates = clean
    extraction.updated_at = datetime.now(UTC)
    extraction.status = "needs_review"
    doc.processing_status = extraction.status
    db.commit()
    return extraction


@router.post("/{document_id}/extraction/confirm")
def confirm_extraction(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_patient_profile: uuid.UUID | None = Header(None),
):
    doc = _document(db, user, document_id, x_patient_profile)
    extraction = _get_extraction(db, doc)
    if extraction.status != "needs_review":
        raise HTTPException(409, "Only reviewed candidates can be confirmed")
    for candidate in extraction.candidates:
        candidate_id = candidate.get("candidate_id") or str(uuid.uuid4())
        candidate["candidate_id"] = candidate_id
        candidate["review_status"] = "confirmed"
        title = f"{candidate['field'].replace('_', ' ').title()}: {candidate['value']}"[:200]
        db.add(
            TimelineEvent(
                profile_id=doc.profile_id,
                source_document_id=doc.id,
                source_extraction_id=extraction.id,
                source_candidate_id=candidate_id,
                source_document_filename=doc.original_filename,
                source_document_checksum=doc.sha256_checksum,
                title=title,
                category="Medical observation",
                event_date=doc.document_date,
                summary=candidate.get("value"),
                source_page=candidate.get("source_page"),
                provenance="patient_confirmed",
                verification_status="confirmed",
            )
        )
    extraction.candidates = list(extraction.candidates)
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
    return extraction


@router.post("/{document_id}/extraction/reject")
def reject_extraction(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_patient_profile: uuid.UUID | None = Header(None),
):
    doc = _document(db, user, document_id, x_patient_profile)
    extraction = _get_extraction(db, doc)
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
    return extraction
