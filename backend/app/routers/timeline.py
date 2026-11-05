from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import AuditEvent, PatientProfile, TimelineEvent, User
from app.profile_access import require_write, resolve_profile

router = APIRouter(prefix="/api/timeline", tags=["medical timeline"])
CATEGORIES = (
    "Consultation",
    "Diagnosis",
    "Prescription",
    "Lab test",
    "Surgery",
    "Admission",
    "Discharge",
    "Allergy",
    "Vaccination",
    "Medical observation",
    "Follow-up",
)


class EventWrite(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    category: str = Field(max_length=40)
    event_date: date | None = None
    summary: str | None = Field(default=None, max_length=5000)
    verification_status: str = "patient_entered"
    conflict_group: str | None = Field(default=None, max_length=80)
    uncertainty_note: str | None = Field(default=None, max_length=1000)


def _profile(
    db: Session, user: User, profile_id: uuid.UUID | None = None
) -> tuple[PatientProfile, str]:
    return resolve_profile(db, user, profile_id)


@router.get("")
def list_events(
    category: str | None = None,
    search: str | None = Query(None, max_length=200),
    source_document_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    verification_status: str | None = None,
    sort: str = "newest",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_patient_profile: uuid.UUID | None = Header(None),
):
    if sort not in {"newest", "oldest"}:
        raise HTTPException(422, "Sort must be newest or oldest")
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "date_from must be on or before date_to")
    if verification_status and verification_status not in {
        "patient_entered",
        "confirmed",
        "uncertain",
        "conflict",
    }:
        raise HTTPException(422, "Unsupported verification status")
    profile, role = _profile(db, user, x_patient_profile)
    q = select(TimelineEvent).where(TimelineEvent.profile_id == profile.id)
    if category:
        q = q.where(TimelineEvent.category == category)
    if source_document_id:
        q = q.where(TimelineEvent.source_document_id == source_document_id)
    if search:
        q = q.where(
            TimelineEvent.title.ilike(f"%{search}%") | TimelineEvent.summary.ilike(f"%{search}%")
        )
    if date_from:
        q = q.where(TimelineEvent.event_date >= date_from)
    if date_to:
        q = q.where(TimelineEvent.event_date <= date_to)
    if verification_status:
        q = q.where(TimelineEvent.verification_status == verification_status)
    order = TimelineEvent.event_date.asc() if sort == "oldest" else TimelineEvent.event_date.desc()
    events = db.scalars(q.order_by(order, TimelineEvent.created_at.desc())).all()
    return [
        {
            **{column.name: getattr(event, column.name) for column in event.__table__.columns},
            "can_edit": role != "viewer",
        }
        for event in events
    ]


def _validate_review_state(payload: EventWrite) -> None:
    if payload.verification_status not in {
        "patient_entered",
        "confirmed",
        "uncertain",
        "conflict",
    }:
        raise HTTPException(422, "Unsupported verification status")
    if payload.verification_status == "conflict" and not payload.conflict_group:
        raise HTTPException(422, "Conflicting events need a shared conflict group")
    if payload.verification_status == "uncertain" and not payload.uncertainty_note:
        raise HTTPException(422, "Uncertain events need an explanation")


@router.post("", status_code=201)
def create_event(
    payload: EventWrite,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_patient_profile: uuid.UUID | None = Header(None),
):
    if payload.category not in CATEGORIES:
        raise HTTPException(422, "Unsupported timeline category")
    _validate_review_state(payload)
    profile, role = _profile(db, user, x_patient_profile)
    require_write(role)
    event = TimelineEvent(
        profile_id=profile.id,
        title=payload.title.strip(),
        category=payload.category,
        event_date=payload.event_date,
        summary=payload.summary,
        provenance="patient_entered",
        verification_status=payload.verification_status,
        conflict_group=payload.conflict_group,
        uncertainty_note=payload.uncertainty_note,
    )
    db.add(event)
    db.add(
        AuditEvent(
            user_id=user.id,
            action="timeline.created",
            target_type="timeline_event",
            target_id=event.id,
        )
    )
    db.commit()
    db.refresh(event)
    return event


@router.get("/{event_id}")
def read_event(
    event_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_patient_profile: uuid.UUID | None = Header(None),
):
    event = db.scalar(
        select(TimelineEvent).where(
            TimelineEvent.id == event_id,
            TimelineEvent.profile_id == _profile(db, user, x_patient_profile)[0].id,
        )
    )
    if event is None:
        raise HTTPException(404, "Timeline event not found")
    return event


@router.put("/{event_id}")
def update_event(
    event_id: uuid.UUID,
    payload: EventWrite,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_patient_profile: uuid.UUID | None = Header(None),
):
    if payload.category not in CATEGORIES:
        raise HTTPException(422, "Unsupported timeline category")
    _validate_review_state(payload)
    event = db.scalar(
        select(TimelineEvent).where(
            TimelineEvent.id == event_id,
            TimelineEvent.profile_id == _profile(db, user, x_patient_profile)[0].id,
        )
    )
    if event is None:
        raise HTTPException(404, "Timeline event not found")
    require_write(_profile(db, user, x_patient_profile)[1])
    event.title = payload.title.strip()
    event.category = payload.category
    event.event_date = payload.event_date
    event.summary = payload.summary
    event.verification_status = payload.verification_status
    event.conflict_group = payload.conflict_group
    event.uncertainty_note = payload.uncertainty_note
    event.updated_at = datetime.now(UTC)
    db.add(
        AuditEvent(
            user_id=user.id,
            action="timeline.updated",
            target_type="timeline_event",
            target_id=event.id,
        )
    )
    db.commit()
    db.refresh(event)
    return event


@router.delete("/{event_id}", status_code=204)
def delete_event(
    event_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_patient_profile: uuid.UUID | None = Header(None),
):
    event = db.scalar(
        select(TimelineEvent).where(
            TimelineEvent.id == event_id,
            TimelineEvent.profile_id == _profile(db, user, x_patient_profile)[0].id,
        )
    )
    if event is None:
        raise HTTPException(404, "Timeline event not found")
    require_write(_profile(db, user, x_patient_profile)[1])
    db.delete(event)
    db.add(
        AuditEvent(
            user_id=user.id,
            action="timeline.deleted",
            target_type="timeline_event",
            target_id=event_id,
        )
    )
    db.commit()
