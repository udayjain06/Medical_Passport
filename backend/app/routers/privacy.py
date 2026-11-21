from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import AuditEvent, ConsentRecord, EmergencyShare, PatientProfile, User

router = APIRouter(prefix="/api/privacy", tags=["privacy"])


def _consent_data(record: ConsentRecord) -> dict:
    return {
        "id": str(record.id),
        "purpose": record.purpose,
        "version": record.version,
        "granted_at": record.granted_at,
        "withdrawn_at": record.withdrawn_at,
    }


@router.get("/consents")
def list_consents(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    records = db.scalars(
        select(ConsentRecord)
        .where(ConsentRecord.user_id == user.id)
        .order_by(ConsentRecord.granted_at.desc())
    ).all()
    return [_consent_data(record) for record in records]


@router.post("/consents/{purpose}/withdraw")
def withdraw_consent(
    purpose: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    if purpose != "emergency_sharing":
        raise HTTPException(
            422, "Terms and privacy consent can only be withdrawn by deleting the account"
        )
    now = datetime.now(UTC)
    active = db.scalars(
        select(ConsentRecord).where(
            ConsentRecord.user_id == user.id,
            ConsentRecord.purpose == purpose,
            ConsentRecord.withdrawn_at.is_(None),
        )
    ).all()
    if not active:
        raise HTTPException(404, "No active consent to withdraw")
    for record in active:
        record.withdrawn_at = now
    owned_profiles = select(PatientProfile.id).where(PatientProfile.user_id == user.id)
    shares = db.scalars(
        select(EmergencyShare).where(
            EmergencyShare.profile_id.in_(owned_profiles), EmergencyShare.revoked_at.is_(None)
        )
    ).all()
    for share in shares:
        share.revoked_at = now
    db.add(AuditEvent(user_id=user.id, action="consent.emergency_sharing.withdrawn"))
    db.commit()
    return {"status": "withdrawn", "revoked_links": len(shares)}


@router.get("/audit")
def list_audit_events(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.user_id == user.id)
        .order_by(AuditEvent.created_at.desc())
        .limit(100)
    ).all()
    return [{"time": event.created_at, "action": event.action} for event in events]
