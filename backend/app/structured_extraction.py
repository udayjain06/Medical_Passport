"""Deterministic, rule-based extraction of medical facts from OCR lines.

Runs offline (no AI provider needed). Every candidate stays "pending" until the patient
accepts it. Rules only copy what is written on the document; nothing is inferred.
"""

from __future__ import annotations

import re
from datetime import date

MONTHS = {
    m: i
    for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1
    )
}
_DATE_PATTERNS = [
    re.compile(r"\b(?P<d>\d{1,2})[/\-.](?P<m>\d{1,2})[/\-.](?P<y>\d{4})\b"),
    re.compile(r"\b(?P<y>\d{4})-(?P<m>\d{1,2})-(?P<d>\d{1,2})\b"),
    re.compile(r"\b(?P<d>\d{1,2})(?:st|nd|rd|th)?[ \-](?P<mon>[A-Za-z]{3,9})[ ,\-]+(?P<y>\d{4})\b"),
]
_DATE_LABELS = [
    ("admission_date", re.compile(r"\b(date of admission|admission date|admitted on|doa)\b", re.I)),
    (
        "discharge_date",
        re.compile(r"\b(date of discharge|discharge date|discharged on|dod)\b", re.I),
    ),
    (
        "follow_up_date",
        re.compile(r"\b(follow[ -]?up|review (?:on|after)|next visit|revisit)\b", re.I),
    ),
    (
        "document_date",
        re.compile(
            r"\b(date|dated|reported on|collected on|report date|reg(?:istration)? date)\b", re.I
        ),
    ),
]
_LABELLED = {
    "diagnosis": re.compile(
        r"^\s*(?:provisional |final |clinical )?(?:diagnosis|dx|impression)\s*[:\-]\s*(.+)$", re.I
    ),
    "condition": re.compile(
        r"^\s*(?:known case of|k/c/o|kco|chronic conditions?|past history|h/o)\s*[:\-]?\s*(.+)$",
        re.I,
    ),
    "allergy": re.compile(
        r"^\s*(?:known |drug |food )?allerg(?:y|ies)\s*[:\-]\s*(.+)$"
        r"|^\s*allergic to\s*[:\-]?\s*(.+)$",
        re.I,
    ),
    "procedure": re.compile(
        r"^\s*(?:procedure|operation|surgery|operative procedure)\s*[:\-]\s*(.+)$", re.I
    ),
}
_NEGATIVE_ALLERGY = re.compile(r"^\s*(nil|none|nka|nkda|no known.*|not known|n/a|-)\s*\.?$", re.I)
_DOCTOR = re.compile(r"\b(Dr\.?\s+[A-Z][A-Za-z.]*(?:\s+[A-Z][A-Za-z.]*){0,3})")
_HOSPITAL = re.compile(
    r"\b(hospital|clinic|nursing home|diagnostics?|laborator(?:y|ies)|pathlab|"
    r"medical cent(?:re|er)|healthcare|health care|polyclinic|institute of)\b",
    re.I,
)
_PATIENT = re.compile(
    r"^\s*(?:patient(?:'s)? name|name of patient|patient|name)\s*[:\-]\s*(.+)$", re.I
)
_MED = re.compile(
    r"^\s*(?:\d{1,2}\s*[.)\-]\s*)?(?:Rx\s*)?(?P<form>tab(?:let)?s?|cap(?:sule)?s?|syp|syrup|inj(?:ection)?|"
    r"oint(?:ment)?|drops?|susp(?:ension)?|gel|cream|inhaler|sachet)\b\.?\s*(?P<body>.+)$",
    re.I,
)
_STRENGTH = re.compile(r"\b\d+(?:\.\d+)?\s?(?:mg|mcg|µg|g|ml|iu|units?|%)\b", re.I)
_FREQ = re.compile(
    r"\b(?:OD|BD|BID|TDS|TID|QID|HS|SOS|PRN|once daily|twice daily|thrice daily|at night|"
    r"morning|\d-\d-\d(?:-\d)?|1\s?\+\s?0\s?\+\s?1|1\s?\+\s?1\s?\+\s?1)\b",
    re.I,
)
_DURATION = re.compile(r"\b(?:x|for)?\s*\d+\s*(?:days?|weeks?|months?|d|wk)\b", re.I)
_LAB = re.compile(
    r"^\s*(?P<test>[A-Za-z][A-Za-z0-9 ()/%\-]{1,40}?)\s*[:\-]?\s+"
    r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>[A-Za-zµ%/][A-Za-z0-9µ%/^.\-]{0,14})?\s*"
    r"(?P<range>\d+(?:\.\d+)?\s*[-–]\s*\d+(?:\.\d+)?)?\s*(?P<flag>\b(?:H|L|High|Low|Abnormal)\b)?\s*$"
)
_KNOWN_TESTS = (
    "hemoglobin",
    "haemoglobin",
    "hb",
    "glucose",
    "fasting blood sugar",
    "hba1c",
    "creatinine",
    "urea",
    "cholesterol",
    "triglycerides",
    "hdl",
    "ldl",
    "tsh",
    "t3",
    "t4",
    "wbc",
    "rbc",
    "platelet",
    "platelets",
    "sgot",
    "sgpt",
    "bilirubin",
    "sodium",
    "potassium",
    "vitamin d",
    "vitamin b12",
    "esr",
    "hematocrit",
    "mcv",
    "mch",
    "mchc",
    "uric acid",
)
EVENT_FIELDS = {
    "diagnosis",
    "condition",
    "allergy",
    "medication",
    "procedure",
    "lab_test",
    "admission_date",
    "discharge_date",
    "follow_up_date",
}


def parse_date(text: str) -> date | None:
    for pattern in _DATE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        parts = match.groupdict()
        try:
            year = int(parts["y"])
            if "mon" in parts and parts["mon"]:
                month = MONTHS.get(parts["mon"][:3].lower())
                if month is None:
                    continue
            else:
                month = int(parts["m"])
            return date(year, month, int(parts["d"]))
        except (ValueError, TypeError):
            continue
    return None


def _candidate(field, value, page, confidence, original=None, normalized=None, weight=0.9):
    return {
        "field": field,
        "value": value.strip()[:2000],
        "source_page": page,
        "original_value": (original or value).strip()[:2000],
        "normalized_value": normalized,
        "confidence": round(max(0.0, min(1.0, confidence * weight)), 3),
        "review_status": "pending",
    }


def _medication(match, page, confidence, line):
    body = match.group("body").strip()
    strength = _STRENGTH.search(body)
    freq = _FREQ.search(body)
    duration = _DURATION.search(body)
    name_end = min([m.start() for m in (strength, freq, duration) if m] or [len(body)])
    name = body[:name_end].strip(" -,.:") or body
    form = match.group("form").title()
    normalized = " | ".join(
        part
        for part in (
            f"{form} {name}".strip(),
            strength.group(0) if strength else "",
            freq.group(0) if freq else "",
            duration.group(0).strip() if duration else "",
        )
        if part
    )
    return _candidate("medication", f"{form}. {body}", page, confidence, line, normalized, 0.85)


def extract_structured(pages: list[dict]) -> list[dict]:
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def add(item: dict) -> None:
        key = (item["field"], item["value"].lower())
        if key not in seen:
            seen.add(key)
            out.append(item)

    for page in pages:
        number = page["page"]
        for line_info in page["lines"]:
            line = line_info["text"].strip()
            conf = float(line_info.get("confidence", 0.5))
            if len(line) < 3:
                continue
            if m := _PATIENT.match(line):
                add(_candidate("patient_name", m.group(1), number, conf, line, weight=0.9))
                continue
            handled = False
            for field, pattern in _LABELLED.items():
                m = pattern.match(line)
                if not m:
                    continue
                value = next(g for g in m.groups() if g).strip()
                handled = True
                if field == "allergy" and _NEGATIVE_ALLERGY.match(value):
                    break
                add(_candidate(field, value, number, conf, line, weight=0.9))
                break
            if handled:
                continue
            if m := _MED.match(line):
                add(_medication(m, number, conf, line))
                continue
            when = parse_date(line)
            if when is not None:
                for field, pattern in _DATE_LABELS:
                    if pattern.search(line):
                        add(
                            _candidate(
                                field, when.isoformat(), number, conf, line, when.isoformat(), 0.9
                            )
                        )
                        break
                continue
            if _HOSPITAL.search(line) and not line[:1].isdigit() and len(line) <= 90:
                add(_candidate("hospital_name", line, number, conf, line, weight=0.7))
                continue
            if m := _DOCTOR.search(line):
                add(_candidate("doctor_name", m.group(1), number, conf, line, weight=0.8))
                continue
            if m := _LAB.match(line):
                test = m.group("test").strip()
                known = any(k in test.lower() for k in _KNOWN_TESTS)
                if m.group("range") or (known and m.group("unit")):
                    value = f"{test}: {m.group('value')} {m.group('unit') or ''}".strip()
                    if m.group("range"):
                        value += f" (ref {m.group('range')})"
                    if m.group("flag"):
                        value += f" [{m.group('flag')}]"
                    add(
                        _candidate(
                            "lab_test",
                            value,
                            number,
                            conf,
                            line,
                            " | ".join(
                                p
                                for p in (
                                    test,
                                    m.group("value"),
                                    m.group("unit") or "",
                                    m.group("range") or "",
                                    m.group("flag") or "",
                                )
                                if p
                            ),
                            0.8,
                        )
                    )
    if not any(item["field"] in EVENT_FIELDS for item in out):
        for page in pages:
            for line_info in page["lines"]:
                text = line_info["text"].strip()
                if len(text) >= 3:
                    add(
                        _candidate(
                            "source_text",
                            text,
                            page["page"],
                            float(line_info.get("confidence", 0.5)),
                            text,
                            weight=1.0,
                        )
                    )
    return out


def names_match(a: str, b: str) -> bool:
    """Loose token-overlap check used to warn when a document names a different person."""

    def tokens(value: str) -> set[str]:
        cleaned = re.sub(r"\b(mr|mrs|ms|miss|master|baby|shri|smt|dr)\b\.?", "", value.lower())
        return {t for t in re.findall(r"[a-z]{2,}", cleaned)}

    left, right = tokens(a), tokens(b)
    if not left or not right:
        return True
    return len(left & right) / min(len(left), len(right)) >= 0.5
