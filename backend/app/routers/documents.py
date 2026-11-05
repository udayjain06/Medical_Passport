from __future__ import annotations

import hashlib
import re
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import document_storage
from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models import AuditEvent, MedicalDocument, PatientProfile, User
from app.profile_access import require_write, resolve_profile

router = APIRouter(prefix="/api/documents", tags=["medical documents"])
CATEGORIES = (
    "Prescription",
    "Laboratory Report",
    "Blood Report",
    "Discharge Summary",
    "Medical Certificate",
    "Imaging Report",
    "Vaccination Record",
    "Other",
)
MIME_TYPES = {"pdf": "application/pdf", "jpg": "image/jpeg", "png": "image/png"}


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    profile_id: uuid.UUID
    original_filename: str
    file_format: str
    file_size: int
    category: str
    document_date: date | None
    processing_status: str
    sha256_checksum: str
    created_at: datetime
    updated_at: datetime
    can_edit: bool = True


class DocumentUpdate(BaseModel):
    category: str | None = Field(default=None, max_length=40)
    document_date: date | None = None


def _profile(
    db: Session, user: User, profile_id: uuid.UUID | None = None
) -> tuple[PatientProfile, str]:
    return resolve_profile(db, user, profile_id)


def _document(
    db: Session, user: User, document_id: uuid.UUID, profile_id: uuid.UUID | None = None
) -> MedicalDocument:
    profile, _role = _profile(db, user, profile_id)
    doc = db.scalar(
        select(MedicalDocument).where(
            MedicalDocument.id == document_id,
            MedicalDocument.profile_id == profile.id,
        )
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


def _detect(data: bytes) -> tuple[str, str]:
    if data.startswith(b"%PDF-") and data.rstrip().endswith(b"%%EOF"):
        return "pdf", MIME_TYPES["pdf"]
    if data.startswith(b"\xff\xd8\xff") and data.endswith(b"\xff\xd9"):
        return "jpg", MIME_TYPES["jpg"]
    if data.startswith(b"\x89PNG\r\n\x1a\n") and b"IEND\xaeB`\x82" in data[-16:]:
        return "png", MIME_TYPES["png"]
    raise HTTPException(status_code=415, detail="File content is not a supported PDF, JPEG, or PNG")


@router.post("", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    category: str = Form("Other"),
    document_date: date | None = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_patient_profile: uuid.UUID | None = Header(None),
):
    if category not in CATEGORIES:
        raise HTTPException(status_code=422, detail="Unsupported document category")
    if file.size is not None and file.size > settings.document_max_size_bytes:
        raise HTTPException(status_code=413, detail="Document exceeds the upload size limit")
    chunks, total = [], 0
    while chunk := await file.read(64 * 1024):
        total += len(chunk)
        if total > settings.document_max_size_bytes:
            raise HTTPException(status_code=413, detail="Document exceeds the upload size limit")
        chunks.append(chunk)
    data = b"".join(chunks)
    fmt, mime = _detect(data)
    if file.content_type != mime:
        raise HTTPException(status_code=415, detail="File MIME type does not match its content")
    profile, role = _profile(db, user, x_patient_profile)
    require_write(role)
    doc_id = uuid.uuid4()
    filename = Path(file.filename or "document").name.replace("\x00", "")
    filename = re.sub(r"[^A-Za-z0-9._ ()-]", "_", filename)[:255] or f"document.{fmt}"
    storage_key = document_storage.save(profile.id, doc_id, data)
    doc = MedicalDocument(
        id=doc_id,
        profile_id=profile.id,
        uploaded_by_user_id=user.id,
        original_filename=filename,
        storage_key=storage_key,
        file_format=fmt,
        file_size=total,
        category=category,
        document_date=document_date,
        sha256_checksum=hashlib.sha256(data).hexdigest(),
    )
    db.add(doc)
    db.add(
        AuditEvent(
            user_id=user.id,
            action="document.uploaded",
            target_type="medical_document",
            target_id=doc.id,
        )
    )
    try:
        db.commit()
    except Exception:
        document_storage.delete(profile.id, doc_id)
        raise
    db.refresh(doc)
    return doc


@router.get("", response_model=list[DocumentRead])
def list_documents(
    category: str | None = Query(None),
    search: str | None = Query(None, max_length=255),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_patient_profile: uuid.UUID | None = Header(None),
):
    profile, role = _profile(db, user, x_patient_profile)
    # Profile authorization is the visibility boundary. The uploader may be another
    # authorized account (for example, a caregiver), so uploader ownership must not
    # hide records from a valid viewer of this profile.
    query = select(MedicalDocument).where(MedicalDocument.profile_id == profile.id)
    if category:
        if category not in CATEGORIES:
            raise HTTPException(status_code=422, detail="Unsupported document category")
        query = query.where(MedicalDocument.category == category)
    if search:
        query = query.where(MedicalDocument.original_filename.ilike(f"%{search}%"))
    documents = db.scalars(query.order_by(MedicalDocument.created_at.desc())).all()
    return [
        {**DocumentRead.model_validate(doc).model_dump(), "can_edit": role != "viewer"}
        for doc in documents
    ]


@router.get("/{document_id}", response_model=DocumentRead)
def document_details(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_patient_profile: uuid.UUID | None = Header(None),
):
    doc = _document(db, user, document_id, x_patient_profile)
    _, role = _profile(db, user, x_patient_profile)
    return {**DocumentRead.model_validate(doc).model_dump(), "can_edit": role != "viewer"}


@router.get("/{document_id}/content")
def document_content(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_patient_profile: uuid.UUID | None = Header(None),
):
    doc = _document(db, user, document_id, x_patient_profile)
    try:
        content = document_storage.read(doc.profile_id, doc.id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Stored document not found") from None
    disposition = "inline" if doc.file_format in {"jpg", "png", "pdf"} else "attachment"
    return Response(
        content,
        media_type=MIME_TYPES[doc.file_format],
        headers={
            "Content-Disposition": f'{disposition}; filename="{doc.original_filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.patch("/{document_id}", response_model=DocumentRead)
def update_document(
    document_id: uuid.UUID,
    payload: DocumentUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_patient_profile: uuid.UUID | None = Header(None),
):
    doc = _document(db, user, document_id, x_patient_profile)
    _, role = _profile(db, user, x_patient_profile)
    require_write(role)
    if "category" in payload.model_fields_set:
        if payload.category not in CATEGORIES:
            raise HTTPException(status_code=422, detail="Unsupported document category")
        doc.category = payload.category
    if "document_date" in payload.model_fields_set:
        doc.document_date = payload.document_date
    doc.updated_at = datetime.now(UTC)
    db.add(
        AuditEvent(
            user_id=user.id,
            action="document.updated",
            target_type="medical_document",
            target_id=doc.id,
        )
    )
    db.commit()
    db.refresh(doc)
    return doc


@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_patient_profile: uuid.UUID | None = Header(None),
):
    doc = _document(db, user, document_id, x_patient_profile)
    _, role = _profile(db, user, x_patient_profile)
    require_write(role)
    db.add(
        AuditEvent(
            user_id=user.id,
            action="document.deleted",
            target_type="medical_document",
            target_id=doc.id,
        )
    )
    profile_id, doc_id = doc.profile_id, doc.id
    db.delete(doc)
    db.commit()
    document_storage.delete(profile_id, doc_id)
    return Response(status_code=204)
