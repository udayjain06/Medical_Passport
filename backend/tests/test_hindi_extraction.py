from app.structured_extraction import extract_structured


def test_rule_extractor_recognizes_common_transliterated_hindi_labels():
    candidates = extract_structured(
        [
            {
                "page": 1,
                "lines": [
                    {"text": "Naam: Asha Rao", "confidence": 0.96},
                    {"text": "Umra: 32 saal", "confidence": 0.9},
                    {"text": "Nidaan: Asthma", "confidence": 0.91},
                    {"text": "Dawa: Tab Metformin 500 mg BD for 10 days", "confidence": 0.94},
                    {"text": "Jaanch: Hemoglobin 12 g/dL", "confidence": 0.92},
                ],
            }
        ]
    )

    by_field = {candidate["field"]: candidate for candidate in candidates}
    assert by_field["patient_name"]["value"] == "Asha Rao"
    assert by_field["age"]["value"] == "32 saal"
    assert by_field["diagnosis"]["value"] == "Asthma"
    assert by_field["medication"]["field"] == "medication"
    assert all(
        part in by_field["medication"]["normalized_value"] for part in ("500 mg", "BD", "10 days")
    )
    assert "Hemoglobin: 12 g/dL" in by_field["lab_test"]["value"]
    assert all(candidate["review_status"] == "pending" for candidate in candidates)


def test_hindi_label_support_does_not_change_english_rule_behavior():
    candidates = extract_structured(
        [
            {
                "page": 1,
                "lines": [
                    {"text": "Patient Name: Mira Shah", "confidence": 0.95},
                    {"text": "Diagnosis: Hypertension", "confidence": 0.9},
                    {"text": "Allergies: NKDA", "confidence": 0.9},
                ],
            }
        ]
    )
    assert {candidate["field"] for candidate in candidates} == {"patient_name", "diagnosis"}
