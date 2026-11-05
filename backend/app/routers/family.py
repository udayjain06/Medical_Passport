from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import AuditEvent, EmergencyShare, PatientProfile, ProfileAccess, User

router = APIRouter(prefix="/api/profiles", tags=["family profiles"])


class DependentCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    relationship_label: str = Field(min_length=1, max_length=60)
    authority_confirmed: bool


class GrantCreate(BaseModel):
    email: EmailStr
    role: str


@router.get("")
def list_profiles(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    owned = list(
        db.scalars(
            select(PatientProfile)
            .where(PatientProfile.user_id == user.id, PatientProfile.archived_at.is_(None))
            .order_by(PatientProfile.is_primary.desc(), PatientProfile.created_at)
        ).all()
    )
    grants = list(db.scalars(select(ProfileAccess).where(ProfileAccess.user_id == user.id)).all())
    result = [
        {"id": str(p.id), "full_name": p.full_name, "is_primary": p.is_primary, "role": "owner"}
        for p in owned
    ]
    for grant in grants:
        profile = db.get(PatientProfile, grant.profile_id)
        if profile is not None and profile.archived_at is None and profile.user_id != user.id:
            result.append(
                {
                    "id": str(profile.id),
                    "full_name": profile.full_name,
                    "is_primary": profile.is_primary,
                    "relationship": profile.relationship_label,
                    "role": grant.role,
                }
            )
    return result


@router.post("", status_code=201)
def create_dependent(
    payload: DependentCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    if not payload.authority_confirmed:
        raise HTTPException(
            422, "Confirm you have consent or lawful authority to manage this dependent profile"
        )
    if not db.scalar(
        select(PatientProfile).where(
            PatientProfile.user_id == user.id, PatientProfile.is_primary.is_(True)
        )
    ):
        raise HTTPException(409, "Create a primary profile first")
    profile = PatientProfile(
        user_id=user.id,
        full_name=payload.full_name.strip(),
        is_primary=False,
        relationship_label=payload.relationship_label.strip(),
    )
    db.add(profile)
    db.flush()
    db.add(
        ProfileAccess(
            profile_id=profile.id, user_id=user.id, role="owner", granted_by_user_id=user.id
        )
    )
    db.add(
        AuditEvent(
            user_id=user.id,
            action="family_profile.created",
            target_type="patient_profile",
            target_id=profile.id,
        )
    )
    db.commit()
    db.refresh(profile)
    return {
        "id": str(profile.id),
        "full_name": profile.full_name,
        "is_primary": False,
        "role": "owner",
        "relationship": payload.relationship_label,
    }


@router.delete("/{profile_id}", status_code=204)
def archive_dependent(
    profile_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.scalar(
        select(PatientProfile).where(
            PatientProfile.id == profile_id,
            PatientProfile.user_id == user.id,
        )
    )
    if profile is None or profile.is_primary:
        raise HTTPException(404, "Dependent profile not found")
    if profile.archived_at is None:
        now = datetime.now(UTC)
        profile.archived_at = now
        for share in db.scalars(
            select(EmergencyShare).where(
                EmergencyShare.profile_id == profile.id,
                EmergencyShare.revoked_at.is_(None),
            )
        ):
            share.revoked_at = now
        for grant in db.scalars(
            select(ProfileAccess).where(ProfileAccess.profile_id == profile.id)
        ):
            db.delete(grant)
        db.add(
            AuditEvent(
                user_id=user.id,
                action="family_profile.archived",
                target_type="patient_profile",
                target_id=profile.id,
            )
        )
        db.commit()


@router.post("/{profile_id}/access", status_code=201)
def grant_access(
    profile_id: uuid.UUID,
    payload: GrantCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.scalar(
        select(PatientProfile).where(
            PatientProfile.id == profile_id, PatientProfile.user_id == user.id
        )
    )
    if not profile:
        raise HTTPException(404, "Profile not found")
    if payload.role not in {"caregiver", "editor", "viewer"}:
        raise HTTPException(422, "Unsupported role")
    target = db.scalar(select(User).where(User.email == str(payload.email).lower()))
    if not target:
        raise HTTPException(
            404, "The invited user must create an account before access can be granted"
        )
    if target.id == user.id:
        raise HTTPException(422, "Owner already has full access")
    grant = db.scalar(
        select(ProfileAccess).where(
            ProfileAccess.profile_id == profile.id, ProfileAccess.user_id == target.id
        )
    )
    if grant:
        grant.role = payload.role
    else:
        db.add(
            ProfileAccess(
                profile_id=profile.id,
                user_id=target.id,
                role=payload.role,
                granted_by_user_id=user.id,
            )
        )
    db.add(
        AuditEvent(
            user_id=user.id,
            action="family_access.granted",
            target_type="patient_profile",
            target_id=profile.id,
        )
    )
    db.commit()
    return {"status": "granted", "email": target.email, "role": payload.role}


@router.delete("/{profile_id}/access/{target_user_id}", status_code=204)
def revoke_access(
    profile_id: uuid.UUID,
    target_user_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.get(PatientProfile, profile_id)
    if not profile:
        raise HTTPException(404, "Profile not found")
    if profile.user_id != user.id and target_user_id != user.id:
        raise HTTPException(404, "Profile not found")
    grant = db.scalar(
        select(ProfileAccess).where(
            ProfileAccess.profile_id == profile_id, ProfileAccess.user_id == target_user_id
        )
    )
    if not grant:
        raise HTTPException(404, "Access grant not found")
    db.delete(grant)
    db.add(
        AuditEvent(
            user_id=user.id,
            action="family_access.revoked",
            target_type="patient_profile",
            target_id=profile.id,
        )
    )
    db.commit()
