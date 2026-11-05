from __future__ import annotations

import base64
import hashlib
import io
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import qrcode
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models import AuditEvent, EmergencyShare, PatientProfile, User
from app.profile_access import require_write, resolve_profile
from app.rate_limit import auth_rate_limiter

router = APIRouter(tags=["emergency sharing"])
FIELDS = {
    "full_name",
    "blood_group",
    "known_allergies",
    "major_conditions",
    "current_medications",
    "emergency_contacts",
}


class ShareCreate(BaseModel):
    fields: list[str] = Field(min_length=1, max_length=6)
    expires_in_hours: int = Field(ge=1, le=720)
    consent: bool


def get_profile(
    db: Session, user: User, profile_id: uuid.UUID | None = None
) -> tuple[PatientProfile, str]:
    return resolve_profile(db, user, profile_id)


@router.post("/api/emergency/shares", status_code=201)
def create_share(
    payload: ShareCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_patient_profile: uuid.UUID | None = Header(None),
):
    if not payload.consent:
        raise HTTPException(422, "Explicit consent is required")
    if len(set(payload.fields)) != len(payload.fields) or not set(payload.fields) <= FIELDS:
        raise HTTPException(422, "Select supported emergency fields")
    profile, role = get_profile(db, user, x_patient_profile)
    require_write(role)
    token = secrets.token_urlsafe(32)
    share = EmergencyShare(
        profile_id=profile.id,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        shared_fields=payload.fields,
        expires_at=datetime.now(UTC) + timedelta(hours=payload.expires_in_hours),
    )
    db.add(share)
    db.add(
        AuditEvent(
            user_id=user.id,
            action="emergency_share.created",
            target_type="emergency_share",
            target_id=share.id,
        )
    )
    db.commit()
    url = f"{settings.public_app_url.rstrip('/')}/emergency/{token}"
    image = qrcode.make(url)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return {
        "id": str(share.id),
        "url": url,
        "qr_png_data_url": "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode(),
        "expires_at": share.expires_at.isoformat(),
    }


@router.get("/api/emergency/shares")
def list_shares(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_patient_profile: uuid.UUID | None = Header(None),
):
    profile, _role = get_profile(db, user, x_patient_profile)
    items = db.scalars(
        select(EmergencyShare)
        .where(EmergencyShare.profile_id == profile.id)
        .order_by(EmergencyShare.created_at.desc())
    ).all()
    return [
        {
            "id": str(item.id),
            "expires_at": item.expires_at.isoformat(),
            "revoked": item.revoked_at is not None,
            "fields": item.shared_fields,
            "created_at": item.created_at.isoformat(),
        }
        for item in items
    ]


@router.delete("/api/emergency/shares/{share_id}", status_code=204)
def revoke_share(
    share_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_patient_profile: uuid.UUID | None = Header(None),
):
    profile, role = get_profile(db, user, x_patient_profile)
    require_write(role)
    share = db.scalar(
        select(EmergencyShare).where(
            EmergencyShare.id == share_id, EmergencyShare.profile_id == profile.id
        )
    )
    if share is None:
        raise HTTPException(404, "Share not found")
    share.revoked_at = datetime.now(UTC)
    db.add(
        AuditEvent(
            user_id=user.id,
            action="emergency_share.revoked",
            target_type="emergency_share",
            target_id=share.id,
        )
    )
    db.commit()


@router.get("/api/public/emergency/{token}")
def public_emergency(token: str, request: Request, db: Session = Depends(get_db)):
    auth_rate_limiter.check(
        f"public-emergency:{request.client.host if request.client else 'unknown'}", 30, 60
    )
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    share = db.scalar(select(EmergencyShare).where(EmergencyShare.token_hash == token_hash))
    now = datetime.now(UTC)
    if share is None or share.revoked_at is not None or share.expires_at.replace(tzinfo=UTC) <= now:
        raise HTTPException(404, "Emergency share not found or expired")
    profile = db.get(PatientProfile, share.profile_id)
    if profile is None:
        raise HTTPException(404, "Emergency share not found or expired")
    allowed = set(share.shared_fields)
    result = {"updated_at": profile.updated_at.isoformat()}
    for field in allowed:
        if field == "emergency_contacts":
            result[field] = [
                {"full_name": c.full_name, "phone_number": c.phone_number}
                for c in profile.emergency_contacts
            ]
        else:
            result[field] = getattr(profile, field)
    db.add(
        AuditEvent(
            user_id=None,
            action="emergency_share.accessed",
            target_type="emergency_share",
            target_id=share.id,
        )
    )
    db.commit()
    return result
