"""Idempotently add the fictional demo patient to the configured local database."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import document_storage
from app.config import settings
from app.demo_fixtures import (
    DEMO_DOCUMENTS,
    DEMO_EMAIL,
    DEMO_PATIENT_NAME,
    DEMO_SIMULATION_ENGINE,
    fixture_bytes,
    fixture_ocr_pages,
)
from app.medical_ai import extract_candidates
from app.models import (
    AuditEvent,
    ConsentRecord,
    DocumentExtraction,
    EmergencyContact,
    EmergencyShare,
    MedicalDocument,
    PatientProfile,
    ProfileAccess,
    TimelineEvent,
    User,
)
from app.routers.emergency import _issue_share
from app.security import hash_password


def _audit_once(
    db: Session,
    user: User,
    action: str,
    target_type: str | None,
    target_id: uuid.UUID | None,
) -> None:
    query = select(AuditEvent.id).where(
        AuditEvent.user_id == user.id,
        AuditEvent.action == action,
        AuditEvent.target_type == target_type,
    )
    query = query.where(
        AuditEvent.target_id.is_(None) if target_id is None else AuditEvent.target_id == target_id
    )
    if db.scalar(query) is None:
        db.add(
            AuditEvent(
                user_id=user.id,
                action=action,
                target_type=target_type,
                target_id=target_id,
            )
        )


def _ensure_consent(db: Session, user: User, purpose: str) -> None:
    active = db.scalar(
        select(ConsentRecord.id).where(
            ConsentRecord.user_id == user.id,
            ConsentRecord.purpose == purpose,
            ConsentRecord.withdrawn_at.is_(None),
        )
    )
    if active is not None:
        return
    record = ConsentRecord(
        user_id=user.id,
        purpose=purpose,
        version="v1",
        granted_at=datetime.now(UTC),
    )
    db.add(record)
    db.flush()
    _audit_once(db, user, "consent.granted", "consent", record.id)


def _get_demo_user(db: Session) -> tuple[User, bool]:
    user = db.scalar(select(User).where(User.email == DEMO_EMAIL))
    if user is not None:
        if not user.is_demo:
            raise RuntimeError(
                "The reserved demo email already belongs to a non-demo account; "
                "no data was changed."
            )
        return user, False

    user = User(
        email=DEMO_EMAIL,
        password_hash=hash_password(secrets.token_urlsafe(48)),
        email_verified_at=datetime.now(UTC),
        is_demo=True,
    )
    db.add(user)
    db.flush()
    _audit_once(db, user, "demo.account_seeded", "user", user.id)
    return user, True


def _get_primary_profile(db: Session, user: User) -> tuple[PatientProfile, bool]:
    profile = db.scalar(
        select(PatientProfile).where(
            PatientProfile.user_id == user.id,
            PatientProfile.is_primary.is_(True),
            PatientProfile.archived_at.is_(None),
        )
    )
    if profile is not None:
        return profile, False

    profile = PatientProfile(
        user_id=user.id,
        is_primary=True,
        full_name=DEMO_PATIENT_NAME,
        date_of_birth=date(2001, 8, 14),
        blood_group="O+",
        known_allergies="Pollen (patient reported); reaction: sneezing and watery eyes",
        major_conditions="Seasonal allergic rhinitis; history of migraine (patient reported)",
        current_medications=(
            "Historical: Cetirizine 10 mg as needed, recorded 21 Nov 2025. "
            "Current medication status is not recorded."
        ),
    )
    db.add(profile)
    db.flush()
    db.add(
        EmergencyContact(
            profile_id=profile.id,
            full_name="Riya Mehta",
            phone_number="+91 00000 00000",
            relationship_label="Sister (fictional demo contact)",
        )
    )
    _audit_once(db, user, "profile.demo_seeded", "patient_profile", profile.id)
    return profile, True


def _ensure_demo_contact(db: Session, user: User, profile: PatientProfile) -> None:
    contact = db.scalar(
        select(EmergencyContact.id).where(
            EmergencyContact.profile_id == profile.id,
            EmergencyContact.full_name == "Riya Mehta",
        )
    )
    if contact is None:
        db.add(
            EmergencyContact(
                profile_id=profile.id,
                full_name="Riya Mehta",
                phone_number="+91 00000 00000",
                relationship_label="Sister (fictional demo contact)",
            )
        )
        db.flush()
        _audit_once(db, user, "profile.demo_contact_seeded", "patient_profile", profile.id)


def _ensure_dependent(db: Session, user: User) -> bool:
    profile = db.scalar(
        select(PatientProfile).where(
            PatientProfile.user_id == user.id,
            PatientProfile.is_primary.is_(False),
            PatientProfile.relationship_label == "Sibling (fictional demo dependent)",
        )
    )
    created = False
    if profile is None:
        profile = PatientProfile(
            user_id=user.id,
            is_primary=False,
            relationship_label="Sibling (fictional demo dependent)",
            full_name="Ira Mehta",
            date_of_birth=date(2005, 3, 9),
        )
        db.add(profile)
        db.flush()
        created = True
    grant = db.scalar(
        select(ProfileAccess.id).where(
            ProfileAccess.profile_id == profile.id,
            ProfileAccess.user_id == user.id,
        )
    )
    if grant is None:
        db.add(
            ProfileAccess(
                profile_id=profile.id,
                user_id=user.id,
                role="owner",
                granted_by_user_id=user.id,
            )
        )
    if created:
        _audit_once(db, user, "family_profile.demo_seeded", "patient_profile", profile.id)
    return created


def _ensure_documents(
    db: Session, user: User, profile: PatientProfile
) -> dict[str, MedicalDocument]:
    documents: dict[str, MedicalDocument] = {}
    new_documents: list[MedicalDocument] = []
    for fixture in DEMO_DOCUMENTS:
        document = db.scalar(
            select(MedicalDocument).where(
                MedicalDocument.profile_id == profile.id,
                MedicalDocument.original_filename == fixture.filename,
            )
        )
        if document is None:
            data = fixture_bytes(fixture)
            document_id = uuid.uuid4()
            storage_key = document_storage.save(profile.id, document_id, data)
            document = MedicalDocument(
                id=document_id,
                profile_id=profile.id,
                uploaded_by_user_id=user.id,
                original_filename=fixture.filename,
                storage_key=storage_key,
                file_format="pdf",
                file_size=len(data),
                category=fixture.category,
                document_date=fixture.document_date,
                sha256_checksum=hashlib.sha256(data).hexdigest(),
            )
            db.add(document)
            new_documents.append(document)
        else:
            path = settings.document_storage_path / str(profile.id) / f"{document.id}.blob"
            if not path.exists():
                # Repair only a missing demo-owned blob. Never overwrite an existing file.
                document_storage.save(profile.id, document.id, fixture_bytes(fixture))
        documents[fixture.filename] = document

    db.flush()
    for document in new_documents:
        _audit_once(db, user, "document.uploaded", "medical_document", document.id)
    return documents


def _candidate_id(profile_id: uuid.UUID, filename: str, field: str) -> str:
    return str(uuid.uuid5(profile_id, f"medical-passport-demo:{filename}:{field}"))


def _ensure_extraction(
    db: Session,
    user: User,
    profile: PatientProfile,
    document: MedicalDocument,
    *,
    confirmed_diagnosis: bool = False,
) -> DocumentExtraction | None:
    existing = db.scalar(
        select(DocumentExtraction).where(DocumentExtraction.document_id == document.id)
    )
    if existing is not None:
        return existing

    fixture = next(
        (item for item in DEMO_DOCUMENTS if item.filename == document.original_filename), None
    )
    if fixture is None:
        return None
    pages = fixture_ocr_pages(fixture)
    candidates, _ = extract_candidates(pages, allow_ai=False)
    if confirmed_diagnosis:
        candidates = [item for item in candidates if item["field"] == "diagnosis"][:1]
        if not candidates:
            return None
        candidates[0]["candidate_id"] = _candidate_id(
            profile.id, document.original_filename, candidates[0]["field"]
        )
        candidates[0]["review_status"] = "confirmed"
        status = "confirmed"
        engine = "seeded synthetic fact, previously patient-reviewed"
    else:
        candidates = [
            {
                **item,
                "candidate_id": _candidate_id(
                    profile.id, document.original_filename, f"{item['field']}:{index}"
                ),
                "review_status": "pending",
            }
            for index, item in enumerate(candidates)
        ]
        status = "needs_review"
        engine = DEMO_SIMULATION_ENGINE

    extraction = DocumentExtraction(
        document_id=document.id,
        profile_id=profile.id,
        status=status,
        ocr_text="\n".join(fixture.lines),
        candidates=candidates,
        engine_version=engine,
    )
    document.processing_status = status
    db.add(extraction)
    db.flush()
    _audit_once(db, user, "document.extraction_seeded", "medical_document", document.id)
    return extraction


def _ensure_timeline(
    db: Session,
    user: User,
    profile: PatientProfile,
    title: str,
    category: str,
    event_date: date,
    summary: str,
    *,
    document: MedicalDocument | None = None,
    extraction: DocumentExtraction | None = None,
    candidate_id: str | None = None,
    provenance: str = "patient_reported",
    status: str = "patient_entered",
) -> bool:
    existing = db.scalar(
        select(TimelineEvent.id).where(
            TimelineEvent.profile_id == profile.id,
            TimelineEvent.title == title,
            TimelineEvent.category == category,
            TimelineEvent.event_date == event_date,
        )
    )
    if existing is not None:
        return False
    event = TimelineEvent(
        profile_id=profile.id,
        source_document_id=document.id if document else None,
        source_extraction_id=extraction.id if extraction else None,
        source_candidate_id=candidate_id,
        source_document_filename=document.original_filename if document else None,
        source_document_checksum=document.sha256_checksum if document else None,
        title=title,
        category=category,
        event_date=event_date,
        summary=summary,
        provenance=provenance,
        verification_status=status,
    )
    db.add(event)
    db.flush()
    _audit_once(db, user, "timeline.demo_seeded", "timeline_event", event.id)
    return True


def seed_demo(db: Session) -> dict[str, int]:
    """Create missing records only for the reserved demo account."""
    if settings.app_env != "development" or not settings.demo_mode:
        raise RuntimeError("Seeding requires APP_ENV=development and DEMO_MODE=true")

    user, created_user = _get_demo_user(db)
    user.email_verified_at = user.email_verified_at or datetime.now(UTC)
    _ensure_consent(db, user, "terms")
    _ensure_consent(db, user, "privacy")
    profile, created_profile = _get_primary_profile(db, user)
    _ensure_demo_contact(db, user, profile)
    created_dependent = _ensure_dependent(db, user)
    documents = _ensure_documents(db, user, profile)

    consultation = documents["demo-consultation-summary.pdf"]
    confirmed_extraction = _ensure_extraction(
        db, user, profile, consultation, confirmed_diagnosis=True
    )
    diagnosis_candidate_id = (
        confirmed_extraction.candidates[0].get("candidate_id")
        if confirmed_extraction and confirmed_extraction.candidates
        else None
    )
    _ensure_timeline(
        db,
        user,
        profile,
        "Patient-reported allergy: Pollen",
        "Allergy",
        date(2025, 8, 4),
        "Reported reaction: sneezing and watery eyes. "
        "Synthetic demo information; not clinical evidence.",
    )
    _ensure_timeline(
        db,
        user,
        profile,
        "Patient-reported history: Migraine",
        "Diagnosis",
        date(2025, 5, 8),
        "Patient-reported history in a fictional sample profile; not clinically verified.",
    )
    _ensure_timeline(
        db,
        user,
        profile,
        "Diagnosis: Seasonal allergic rhinitis",
        "Diagnosis",
        date(2026, 2, 12),
        "Synthetic demo fact previously reviewed in this fictional record; not clinical evidence.",
        document=consultation,
        extraction=confirmed_extraction,
        candidate_id=diagnosis_candidate_id,
        provenance="patient_confirmed",
        status="confirmed",
    )
    _ensure_extraction(
        db,
        user,
        profile,
        documents["demo-historical-prescription.pdf"],
    )

    active_share = db.scalar(
        select(EmergencyShare).where(
            EmergencyShare.profile_id == profile.id,
            EmergencyShare.created_by_user_id == user.id,
            EmergencyShare.revoked_at.is_(None),
            EmergencyShare.expires_at > datetime.now(UTC),
        )
    )
    created_share = active_share is None
    if active_share is None:
        _issue_share(
            db,
            user,
            profile,
            [
                "full_name",
                "blood_group",
                "known_allergies",
                "major_conditions",
                "emergency_contacts",
            ],
            min(24, settings.emergency_max_hours),
            "Synthetic demo wallet card",
        )
    else:
        _ensure_consent(db, user, "emergency_sharing")

    db.commit()
    return {
        "created_user": int(created_user),
        "created_primary_profile": int(created_profile),
        "created_dependent_profile": int(created_dependent),
        "documents_present": len(documents),
        "created_emergency_share": int(created_share),
    }


def main() -> None:
    from app.database import SessionLocal

    if settings.app_env != "development" or not settings.demo_mode:
        raise SystemExit("Refusing to seed: set APP_ENV=development and DEMO_MODE=true locally.")
    with SessionLocal() as db:
        result = seed_demo(db)
    print("Demo seed finished without replacing existing records.")
    for label, count in result.items():
        print(f"{label}={count}")


if __name__ == "__main__":
    main()
