from app.structured_extraction import extract_structured


def test_transliterated_hindi_labels_extract_supported_facts():
    pages = [
        {
            "page": 1,
            "lines": [
                {"text": "Naam: Meera Rao", "confidence": 0.95},
                {"text": "Umra: 42 years", "confidence": 0.95},
                {"text": "Dawa: Metformin 500 mg BD", "confidence": 0.95},
                {"text": "Jaanch: HbA1c 6.5 %", "confidence": 0.95},
                {"text": "Nidaan: Type 2 diabetes", "confidence": 0.95},
            ],
        }
    ]
    candidates = extract_structured(pages)
    assert {candidate["field"] for candidate in candidates} == {
        "patient_name",
        "age",
        "medication",
        "lab_test",
        "diagnosis",
    }
    assert (
        next(item for item in candidates if item["field"] == "patient_name")["value"] == "Meera Rao"
    )
    assert (
        next(item for item in candidates if item["field"] == "diagnosis")["value"]
        == "Type 2 diabetes"
    )
