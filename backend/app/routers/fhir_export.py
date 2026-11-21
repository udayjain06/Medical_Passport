import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import PatientProfile, TimelineEvent, User
from app.profile_access import resolve_profile

router = APIRouter(tags=["FHIR export"])


def _extension(event: TimelineEvent) -> list[dict]:
    details = {
        "document": event.source_document_filename,
        "sha256": event.source_document_checksum,
        "page": event.source_page,
        "recordedAt": event.created_at.isoformat(),
    }
    return [
        {
            "url": f"https://medical-passport.example/fhir/StructureDefinition/source-{key}",
            "valueString" if isinstance(value, str) else "valueInteger": value,
        }
        for key, value in details.items()
        if value is not None
    ]


def _base(event: TimelineEvent, resource_type: str) -> dict:
    return {
        "resourceType": resource_type,
        "id": str(event.id),
        "meta": {"source": "https://medical-passport.example", "extension": _extension(event)},
    }


def build_bundle(profile: PatientProfile, events: list[TimelineEvent]) -> dict:
    patient = {
        "resourceType": "Patient",
        "id": str(profile.id),
        "name": [{"text": profile.full_name}],
    }
    resources = [patient]
    for event in events:
        text = event.summary or event.title
        if event.category.lower() == "allergy":
            resource = _base(event, "AllergyIntolerance")
            resource.update(
                {
                    "clinicalStatus": {"text": "active"},
                    "code": {"text": text},
                    "patient": {"reference": f"Patient/{profile.id}"},
                }
            )
        elif event.category.lower() in {"diagnosis", "condition"}:
            resource = _base(event, "Condition")
            resource.update(
                {
                    "clinicalStatus": {"text": "active"},
                    "code": {"text": text},
                    "subject": {"reference": f"Patient/{profile.id}"},
                }
            )
        elif event.category.lower() in {"prescription", "medication"}:
            resource = _base(event, "MedicationStatement")
            resource.update(
                {
                    "status": "active",
                    "medicationCodeableConcept": {"text": text},
                    "subject": {"reference": f"Patient/{profile.id}"},
                }
            )
        elif event.category.lower() in {"surgery", "procedure"}:
            resource = _base(event, "Procedure")
            resource.update(
                {
                    "status": "completed",
                    "code": {"text": text},
                    "subject": {"reference": f"Patient/{profile.id}"},
                }
            )
        else:
            resource = _base(event, "Observation")
            resource.update(
                {
                    "status": "final",
                    "code": {"text": event.title},
                    "subject": {"reference": f"Patient/{profile.id}"},
                    "valueString": text,
                }
            )
        if event.event_date:
            date_field = {
                "AllergyIntolerance": "onsetDateTime",
                "Condition": "onsetDateTime",
                "MedicationStatement": "effectiveDateTime",
                "Observation": "effectiveDateTime",
                "Procedure": "performedDateTime",
            }.get(resource["resourceType"])
            if date_field:
                resource[date_field] = event.event_date.isoformat()
        resources.append(resource)
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "meta": {"profile": ["http://hl7.org/fhir/R4/Bundle"]},
        "entry": [
            {"fullUrl": f"urn:uuid:{resource['id']}", "resource": resource}
            for resource in resources
        ],
    }


@router.get("/api/export/fhir")
def export_fhir(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_patient_profile: uuid.UUID | None = Header(None),
):
    profile, _role = resolve_profile(db, user, x_patient_profile)
    if profile.user_id != user.id:
        raise HTTPException(403, "FHIR export is available to the profile owner")
    events = db.scalars(
        select(TimelineEvent)
        .where(
            TimelineEvent.profile_id == profile.id,
            TimelineEvent.verification_status == "confirmed",
            TimelineEvent.provenance == "patient_confirmed",
            TimelineEvent.conflict_group.is_(None),
        )
        .order_by(TimelineEvent.event_date, TimelineEvent.created_at)
    ).all()
    return build_bundle(profile, events)
