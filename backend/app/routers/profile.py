from uuid import UUID

from fastapi import APIRouter, Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.dependencies import get_current_user
from app.models import AuditEvent, EmergencyContact, PatientProfile, User
from app.profile_access import require_write, resolve_profile
from app.schemas import PatientProfileRead, PatientProfileWrite

router = APIRouter(prefix="/api/profile", tags=["patient profile"])


def _profile_for_user(db: Session, user: User, profile_id: UUID | None = None) -> PatientProfile:
    profile, _role = resolve_profile(db, user, profile_id)
    return db.scalar(
        select(PatientProfile)
        .options(selectinload(PatientProfile.emergency_contacts))
        .where(PatientProfile.id == profile.id)
    )


@router.get("", response_model=PatientProfileRead)
def read_profile(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_patient_profile: UUID | None = Header(None),
) -> PatientProfile:
    return _profile_for_user(db, user, x_patient_profile)


@router.put("", response_model=PatientProfileRead)
def write_profile(
    payload: PatientProfileWrite,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_patient_profile: UUID | None = Header(None),
) -> PatientProfile:
    profile, role = resolve_profile(db, user, x_patient_profile)
    require_write(role)
    profile = _profile_for_user(db, user, x_patient_profile)
    if profile is None:
        profile = PatientProfile(user_id=user.id, full_name=payload.full_name)
        db.add(profile)
        db.flush()

    profile.full_name = payload.full_name
    profile.date_of_birth = payload.date_of_birth
    profile.blood_group = payload.blood_group
    profile.phone_number = payload.phone_number
    profile.known_allergies = payload.known_allergies
    profile.major_conditions = payload.major_conditions
    profile.current_medications = payload.current_medications
    profile.emergency_contacts.clear()
    profile.emergency_contacts.extend(
        EmergencyContact(**contact.model_dump()) for contact in payload.emergency_contacts
    )
    db.add(
        AuditEvent(
            user_id=user.id,
            action="profile.updated",
            target_type="patient_profile",
            target_id=profile.id,
        )
    )
    db.commit()
    return _profile_for_user(db, user, profile.id)
