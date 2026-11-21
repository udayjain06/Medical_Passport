import uuid

from app.models import TimelineEvent

from test_phase1 import ORIGIN, register


def test_fhir_bundle_contains_required_confirmed_resources_and_excludes_others(client):
    assert register(client, "fhir@example.com").status_code == 201
    profile_id = client.get("/api/profile").json()["id"]
    with client.app.state.test_sessions() as db:
        for category, title, status, conflict in (
            ("Allergy", "Allergy: Penicillin", "confirmed", None),
            ("Diagnosis", "Diagnosis: Asthma", "confirmed", None),
            ("Prescription", "Medication: Metformin", "confirmed", None),
            ("Lab test", "Lab: HbA1c", "confirmed", None),
            ("Procedure", "Procedure: X-ray", "confirmed", None),
            ("Diagnosis", "Diagnosis: Conflict", "confirmed", "conflict-1"),
            ("Diagnosis", "Diagnosis: Pending", "pending", None),
        ):
            db.add(
                TimelineEvent(
                    id=uuid.uuid4(),
                    profile_id=uuid.UUID(profile_id),
                    title=title,
                    category=category,
                    summary=title,
                    provenance="patient_confirmed",
                    verification_status=status,
                    conflict_group=conflict,
                )
            )
        db.commit()

    response = client.get("/api/export/fhir", headers=ORIGIN)
    assert response.status_code == 200
    bundle = response.json()
    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "collection"
    resources = [entry["resource"] for entry in bundle["entry"]]
    assert {resource["resourceType"] for resource in resources} == {
        "Patient",
        "AllergyIntolerance",
        "Condition",
        "MedicationStatement",
        "Observation",
        "Procedure",
    }
    allergy = next(
        resource for resource in resources if resource["resourceType"] == "AllergyIntolerance"
    )
    assert allergy["patient"]["reference"].startswith("Patient/")
    assert allergy["code"]["text"] == "Allergy: Penicillin"
    assert allergy["meta"]["source"]
    assert "subject" in next(
        resource for resource in resources if resource["resourceType"] == "Condition"
    )
    medication = next(
        resource for resource in resources if resource["resourceType"] == "MedicationStatement"
    )
    assert medication["status"] and medication["medicationCodeableConcept"]["text"]
    observation = next(
        resource for resource in resources if resource["resourceType"] == "Observation"
    )
    assert observation["status"] and observation["code"]["text"]
    procedure = next(resource for resource in resources if resource["resourceType"] == "Procedure")
    assert procedure["status"] and procedure["subject"]["reference"]
    assert "Diagnosis: Pending" not in str(bundle)
    assert "Diagnosis: Conflict" not in str(bundle)
