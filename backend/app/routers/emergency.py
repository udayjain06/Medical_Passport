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
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models import (
    AuditEvent,
    EmergencyAccessLog,
    EmergencyShare,
    PatientProfile,
    TimelineEvent,
    User,
)
from app.network import client_ip
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
    expires_in_hours: int = Field(ge=1, le=87600)
    consent: bool
    label: str | None = Field(default=None, max_length=80)


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
    if payload.expires_in_hours > settings.emergency_max_hours:
        raise HTTPException(422, f"Links can last at most {settings.emergency_max_hours} hours")
    profile, role = get_profile(db, user, x_patient_profile)
    require_write(role)
    return _issue_share(db, user, profile, payload.fields, payload.expires_in_hours, payload.label)


def _issue_share(
    db: Session,
    user: User,
    profile: PatientProfile,
    fields: list[str],
    hours: int,
    label: str | None,
    action: str = "emergency_share.created",
) -> dict:
    token = secrets.token_urlsafe(32)
    share = EmergencyShare(
        profile_id=profile.id,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        shared_fields=fields,
        expires_at=datetime.now(UTC) + timedelta(hours=hours),
        label=(label or "").strip() or None,
    )
    db.add(share)
    db.flush()
    db.add(
        AuditEvent(
            user_id=user.id, action=action, target_type="emergency_share", target_id=share.id
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
        "label": share.label,
        "patient_name": profile.full_name,
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
    stats = {
        row[0]: (row[1], row[2])
        for row in db.execute(
            select(
                EmergencyAccessLog.share_id,
                func.count(EmergencyAccessLog.id),
                func.max(EmergencyAccessLog.accessed_at),
            )
            .where(EmergencyAccessLog.share_id.in_([i.id for i in items] or [None]))
            .group_by(EmergencyAccessLog.share_id)
        )
    }
    return [
        {
            "id": str(item.id),
            "expires_at": item.expires_at.isoformat(),
            "revoked": item.revoked_at is not None,
            "fields": item.shared_fields,
            "created_at": item.created_at.isoformat(),
            "label": item.label,
            "access_count": stats.get(item.id, (0, None))[0],
            "last_accessed_at": (
                stats[item.id][1].isoformat() if item.id in stats and stats[item.id][1] else None
            ),
        }
        for item in items
    ]


def _owned_share(db: Session, profile: PatientProfile, share_id: uuid.UUID) -> EmergencyShare:
    share = db.scalar(
        select(EmergencyShare).where(
            EmergencyShare.id == share_id, EmergencyShare.profile_id == profile.id
        )
    )
    if share is None:
        raise HTTPException(404, "Share not found")
    return share


@router.get("/api/emergency/shares/{share_id}/access-log")
def access_log(
    share_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_patient_profile: uuid.UUID | None = Header(None),
):
    profile, role = get_profile(db, user, x_patient_profile)
    require_write(role)
    share = _owned_share(db, profile, share_id)
    rows = db.scalars(
        select(EmergencyAccessLog)
        .where(EmergencyAccessLog.share_id == share.id)
        .order_by(EmergencyAccessLog.accessed_at.desc())
        .limit(200)
    ).all()
    return [
        {
            "accessed_at": r.accessed_at.isoformat(),
            "ip_prefix": r.ip_prefix,
            "user_agent": r.user_agent,
        }
        for r in rows
    ]


class RenewPayload(BaseModel):
    expires_in_hours: int = Field(ge=1, le=87600)
    consent: bool


@router.post("/api/emergency/shares/{share_id}/renew", status_code=201)
def renew_share(
    share_id: uuid.UUID,
    payload: RenewPayload,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_patient_profile: uuid.UUID | None = Header(None),
):
    """Rotate a link: issue a fresh token/QR with the same fields and revoke the old one."""
    if not payload.consent:
        raise HTTPException(422, "Explicit consent is required")
    if payload.expires_in_hours > settings.emergency_max_hours:
        raise HTTPException(422, f"Links can last at most {settings.emergency_max_hours} hours")
    profile, role = get_profile(db, user, x_patient_profile)
    require_write(role)
    old = _owned_share(db, profile, share_id)
    old.revoked_at = old.revoked_at or datetime.now(UTC)
    return _issue_share(
        db,
        user,
        profile,
        list(old.shared_fields),
        payload.expires_in_hours,
        old.label,
        "emergency_share.renewed",
    )


@router.delete("/api/emergency/shares/{share_id}", status_code=204)
def revoke_share(
    share_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_patient_profile: uuid.UUID | None = Header(None),
):
    profile, role = get_profile(db, user, x_patient_profile)
    require_write(role)
    share = _owned_share(db, profile, share_id)
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


DOCUMENT_FACT_FIELDS = {
    "known_allergies": ("document_allergies", "Allergy", None),
    "major_conditions": ("document_conditions", "Diagnosis", None),
    # Prescriptions go stale, so only recent ones are surfaced and always shown with their date.
    "current_medications": ("document_medications", "Prescription", 180),
}


def document_facts(db: Session, profile_id: uuid.UUID, fields: set[str]) -> dict[str, list[dict]]:
    """Patient-confirmed facts from uploaded records, kept apart from the typed profile."""
    out: dict[str, list[dict]] = {}
    today = datetime.now(UTC).date()
    for field, (key, category, max_age_days) in DOCUMENT_FACT_FIELDS.items():
        if field not in fields:
            continue
        events = db.scalars(
            select(TimelineEvent)
            .where(
                TimelineEvent.profile_id == profile_id,
                TimelineEvent.category == category,
                TimelineEvent.verification_status == "confirmed",
                TimelineEvent.source_candidate_id.is_not(None),
            )
            .order_by(TimelineEvent.event_date.desc().nulls_last())
            .limit(25)
        ).all()
        items = []
        for event in events:
            if max_age_days is not None and (
                event.event_date is None or (today - event.event_date).days > max_age_days
            ):
                continue
            items.append(
                {
                    "text": (event.summary or event.title).split(" — ")[0],
                    "record_date": event.event_date.isoformat() if event.event_date else None,
                }
            )
        if items:
            out[key] = items
    return out


@router.get("/api/public/emergency/{token}")
def public_emergency(token: str, request: Request, db: Session = Depends(get_db)):
    ip = client_ip(request)
    auth_rate_limiter.check(
        f"public-emergency:{ip}",
        settings.emergency_access_rate_per_minute,
        60,
        "Too many emergency lookups from this network. Try again in a minute.",
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
    result.update(document_facts(db, profile.id, allowed))
    # Store only a coarse network prefix, never the full address.
    prefix = ".".join(ip.split(".")[:3]) + ".x" if ip.count(".") == 3 else ip.split(":")[0] + "::"
    db.add(
        EmergencyAccessLog(
            share_id=share.id,
            ip_prefix=prefix[:64],
            user_agent=(request.headers.get("user-agent") or "")[:160] or None,
        )
    )
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
