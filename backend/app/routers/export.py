from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import PatientProfile, TimelineEvent, User
from app.profile_access import resolve_profile

router = APIRouter(prefix="/api/export", tags=["data export"])
FHIR_SOURCE = "urn:medical-passport:fhir"


def _provenance(event: TimelineEvent) -> list[dict]:
    extensions = [
        {
            "url": f"{FHIR_SOURCE}/source-timeline-event",
            "valueString": str(event.id),
        }
    ]
    if event.source_document_filename:
        extensions.append(
            {
                "url": f"{FHIR_SOURCE}/source-document-name",
                "valueString": event.source_document_filename,
            }
        )
    if event.source_document_checksum:
        extensions.append(
            {
                "url": f"{FHIR_SOURCE}/source-document-sha256",
                "valueString": event.source_document_checksum,
            }
        )
    return extensions


def _resource_meta(event: TimelineEvent) -> dict:
    return {
        "source": (
            f"urn:uuid:{event.source_document_id}"
            if event.source_document_id
            else "urn:medical-passport:timeline"
        ),
        "extension": _provenance(event),
    }


def _resource_for_event(event: TimelineEvent, patient_id: UUID) -> dict | None:
    common = {"id": str(event.id), "meta": _resource_meta(event)}
    text = event.summary or event.title
    code = {"text": text}
    date_value = event.event_date.isoformat() if event.event_date else None
    category = event.category.strip().lower()
    patient_ref = {"reference": f"Patient/{patient_id}"}

    if category == "allergy":
        return {
            "resourceType": "AllergyIntolerance",
            **common,
            "patient": patient_ref,
            "clinicalStatus": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical",
                        "code": "active",
                    }
                ]
            },
            "verificationStatus": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-verification",
                        "code": "unconfirmed",
                    }
                ]
            },
            "code": code,
            "note": [
                {
                    "text": (
                        "Patient-confirmed timeline entry; clinical status was not "
                        "separately recorded."
                    )
                }
            ],
            **({"recordedDate": date_value} if date_value else {}),
        }
    if category in {"diagnosis", "condition"}:
        return {
            "resourceType": "Condition",
            **common,
            "subject": patient_ref,
            "verificationStatus": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                        "code": "unconfirmed",
                    }
                ]
            },
            "code": {"text": event.title},
            **({"note": [{"text": event.summary}]} if event.summary else {}),
            **({"onsetDateTime": date_value} if date_value else {}),
        }
    if category in {"prescription", "medication"}:
        return {
            "resourceType": "MedicationStatement",
            **common,
            "subject": patient_ref,
            "informationSource": patient_ref,
            "status": "unknown",
            "medicationCodeableConcept": code,
            **({"effectiveDateTime": date_value} if date_value else {}),
        }
    if category in {"lab test", "medical observation"}:
        return {
            "resourceType": "Observation",
            **common,
            "subject": patient_ref,
            "status": "unknown",
            "code": {"text": event.title},
            "valueString": text,
            **({"effectiveDateTime": date_value} if date_value else {}),
        }
    if category in {"surgery", "procedure"}:
        return {
            "resourceType": "Procedure",
            **common,
            "subject": patient_ref,
            "status": "unknown",
            "code": code,
            **({"performedDateTime": date_value} if date_value else {}),
        }
    return None


def build_bundle(profile: PatientProfile, events: list[TimelineEvent]) -> dict:
    patient = {
        "resourceType": "Patient",
        "id": str(profile.id),
        "meta": {
            "source": "urn:medical-passport:patient-profile",
            "extension": [
                {
                    "url": f"{FHIR_SOURCE}/source-profile",
                    "valueString": "Patient profile; demographics are patient-reported.",
                }
            ],
        },
        "name": [{"text": profile.full_name}],
    }
    if profile.date_of_birth:
        patient["birthDate"] = profile.date_of_birth.isoformat()

    resources = [patient]
    resources.extend(
        resource
        for event in events
        if (resource := _resource_for_event(event, profile.id)) is not None
    )
    entries = [
        {"fullUrl": f"urn:uuid:{resource['id']}", "resource": resource} for resource in resources
    ]
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "timestamp": datetime.now(UTC).isoformat(),
        "total": len(entries),
        "entry": entries,
    }


@router.get("/fhir")
def export_fhir(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_patient_profile: UUID | None = Header(None),
) -> dict:
    profile, _role = resolve_profile(db, user, x_patient_profile)
    events = db.scalars(
        select(TimelineEvent)
        .where(
            TimelineEvent.profile_id == profile.id,
            TimelineEvent.verification_status == "confirmed",
            TimelineEvent.conflict_group.is_(None),
            TimelineEvent.uncertainty_note.is_(None),
        )
        .order_by(TimelineEvent.event_date.asc().nulls_last(), TimelineEvent.created_at.asc())
    ).all()
    return build_bundle(profile, events)
