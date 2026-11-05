from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PatientProfile, ProfileAccess, User


def resolve_profile(
    db: Session, user: User, profile_id: UUID | None = None
) -> tuple[PatientProfile, str]:
    if profile_id is None:
        profile = db.scalar(
            select(PatientProfile).where(
                PatientProfile.user_id == user.id,
                PatientProfile.is_primary.is_(True),
                PatientProfile.archived_at.is_(None),
            )
        )
        if profile is None:
            profile = db.scalar(
                select(PatientProfile)
                .where(
                    PatientProfile.user_id == user.id,
                    PatientProfile.archived_at.is_(None),
                )
                .order_by(PatientProfile.created_at)
            )
        if profile is None:
            raise HTTPException(404, "Patient profile not found")
        return profile, "owner"
    profile = db.get(PatientProfile, profile_id)
    if profile is None or profile.archived_at is not None:
        raise HTTPException(404, "Patient profile not found")
    if profile.user_id == user.id:
        return profile, "owner"
    access = db.scalar(
        select(ProfileAccess).where(
            ProfileAccess.profile_id == profile.id, ProfileAccess.user_id == user.id
        )
    )
    if access is None:
        raise HTTPException(404, "Patient profile not found")
    return profile, access.role


def require_write(role: str) -> None:
    if role not in {"owner", "caregiver", "editor"}:
        raise HTTPException(403, "This profile is read-only for your account")
