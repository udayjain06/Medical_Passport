from datetime import date
from uuid import UUID

from app.models import TimelineEvent

from test_phase1 import register


def test_fhir_export_contains_only_patient_confirmed_nonconflicted_events(client):
    assert register(client, "fhir-export@example.com", "Mira Shah").status_code == 201
    profile = client.get("/api/profile").json()
    profile_id = UUID(profile["id"])

    with client.app.state.test_sessions() as db:
        events = [
            TimelineEvent(
                profile_id=profile_id,
                source_document_filename="synthetic-lab-report.pdf",
                source_document_checksum="a" * 64,
                title=title,
                category=category,
                event_date=date(2025, 4, 3),
                summary=summary,
                provenance="patient_confirmed",
                verification_status="confirmed",
            )
            for title, category, summary in (
                ("Allergy: penicillin", "Allergy", "Patient reports penicillin allergy"),
                ("Diagnosis: asthma", "Diagnosis", "Asthma reported in source record"),
                ("Medication: salbutamol", "Prescription", "Inhaler as listed on prescription"),
                ("Lab: haemoglobin", "Lab test", "Haemoglobin: 12 g/dL"),
                ("Procedure: appendectomy", "Surgery", "Appendectomy in source record"),
            )
        ]
        events.extend(
            [
                TimelineEvent(
                    profile_id=profile_id,
                    title="Pending diagnosis: should not export",
                    category="Diagnosis",
                    provenance="patient_entered",
                    verification_status="patient_entered",
                ),
                TimelineEvent(
                    profile_id=profile_id,
                    title="Conflicted allergy: should not export",
                    category="Allergy",
                    provenance="patient_entered",
                    verification_status="confirmed",
                    conflict_group="allergy-review",
                ),
                TimelineEvent(
                    profile_id=profile_id,
                    title="Uncertain procedure: should not export",
                    category="Surgery",
                    provenance="patient_entered",
                    verification_status="confirmed",
                    uncertainty_note="Date is unclear",
                ),
            ]
        )
        db.add_all(events)
        db.commit()
        source_event_id = str(events[3].id)

    response = client.get("/api/export/fhir")
    assert response.status_code == 200, response.text
    bundle = response.json()
    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "collection"
    assert bundle["total"] == len(bundle["entry"])
    resources = [entry["resource"] for entry in bundle["entry"]]
    types = {resource["resourceType"] for resource in resources}
    assert {
        "Patient",
        "AllergyIntolerance",
        "Condition",
        "MedicationStatement",
        "Observation",
        "Procedure",
    } == types
    assert "should not export" not in str(bundle)

    patient = next(resource for resource in resources if resource["resourceType"] == "Patient")
    assert patient["name"][0]["text"] == "Mira Shah"
    assert patient["id"] == str(profile_id)
    for resource in resources:
        assert resource["meta"]["source"]
        if resource["resourceType"] == "AllergyIntolerance":
            assert resource["patient"]["reference"] == f"Patient/{profile_id}"
            assert resource["clinicalStatus"]["coding"][0]["code"] == "active"
            assert resource["verificationStatus"]["coding"][0]["code"] == "unconfirmed"
            assert resource["code"]["text"]
            assert "not separately recorded" in resource["note"][0]["text"]
        elif resource["resourceType"] == "Condition":
            assert resource["subject"]["reference"] == f"Patient/{profile_id}"
            assert resource["verificationStatus"]["coding"][0]["code"] == "unconfirmed"
            assert resource["code"]["text"]
        elif resource["resourceType"] == "MedicationStatement":
            assert resource["status"] == "unknown"
            assert resource["subject"]["reference"] == f"Patient/{profile_id}"
            assert resource["medicationCodeableConcept"]["text"]
        elif resource["resourceType"] == "Observation":
            assert resource["status"] == "unknown"
            assert resource["subject"]["reference"] == f"Patient/{profile_id}"
            assert resource["code"]["text"] and resource["valueString"]
            assert source_event_id in {
                item["valueString"] for item in resource["meta"]["extension"]
            }
        elif resource["resourceType"] == "Procedure":
            assert resource["status"] == "unknown"
            assert resource["subject"]["reference"] == f"Patient/{profile_id}"
            assert resource["code"]["text"]
