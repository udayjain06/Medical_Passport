"""Deterministic documents used only by the local synthetic demo."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date

DEMO_EMAIL = "demo@medicalpassport.local"
DEMO_PATIENT_NAME = "Aarav Mehta"
DEMO_SIMULATION_ENGINE = "DEMO EXTRACTION SIMULATION (synthetic fixture rules-v1)"


@dataclass(frozen=True)
class DemoDocument:
    filename: str
    category: str
    document_date: date
    lines: tuple[str, ...]


DEMO_DOCUMENTS = (
    DemoDocument(
        filename="demo-cbc-report.pdf",
        category="Blood Report",
        document_date=date(2026, 1, 15),
        lines=(
            "SYNTHETIC TEST DOCUMENT — NOT FOR CLINICAL USE",
            "CBC Report - Complete Blood Count",
            "Patient name: Aarav Mehta",
            "Date: 15 Jan 2026",
            "Investigation: Complete Blood Count",
            "Hemoglobin: 14.1 g/dL",
            "WBC: 6.2 10^9/L",
            "Platelets: 250 10^9/L",
        ),
    ),
    DemoDocument(
        filename="demo-lipid-profile.pdf",
        category="Laboratory Report",
        document_date=date(2025, 12, 14),
        lines=(
            "SYNTHETIC TEST DOCUMENT — NOT FOR CLINICAL USE",
            "Lipid Profile",
            "Patient name: Aarav Mehta",
            "Date: 14 Dec 2025",
            "Investigation: Lipid profile",
            "Total cholesterol: 172 mg/dL",
            "HDL: 48 mg/dL",
            "LDL: 101 mg/dL",
            "Triglycerides: 116 mg/dL",
        ),
    ),
    DemoDocument(
        filename="demo-thyroid-profile.pdf",
        category="Laboratory Report",
        document_date=date(2025, 8, 4),
        lines=(
            "SYNTHETIC TEST DOCUMENT — NOT FOR CLINICAL USE",
            "Thyroid Profile",
            "Patient name: Aarav Mehta",
            "Date: 04 Aug 2025",
            "Investigation: Thyroid profile",
            "TSH: 2.1 uIU/mL",
            "T3: 1.2 ng/mL",
            "T4: 8.4 ug/dL",
        ),
    ),
    DemoDocument(
        filename="demo-consultation-summary.pdf",
        category="Discharge Summary",
        document_date=date(2026, 2, 12),
        lines=(
            "SYNTHETIC TEST DOCUMENT — NOT FOR CLINICAL USE",
            "Consultation Summary",
            "Patient name: Aarav Mehta",
            "Date: 12 Feb 2026",
            "Dr. Nisha Rao",
            "Sample Community Clinic - DEMO FACILITY",
            "Diagnosis: Seasonal allergic rhinitis",
            "Past history: Migraine",
            "Follow-up: 12 Mar 2026",
        ),
    ),
    DemoDocument(
        filename="demo-historical-prescription.pdf",
        category="Prescription",
        document_date=date(2025, 11, 21),
        lines=(
            "SYNTHETIC TEST DOCUMENT — NOT FOR CLINICAL USE",
            "Historical Consultation Prescription",
            "Patient name: Aarav Mehta",
            "Date: 21 Nov 2025",
            "Dr. Nisha Rao",
            "Sample Community Clinic - DEMO FACILITY",
            "Medication: Tab. Cetirizine 10 mg PRN",
            "Historical entry - current medication status not recorded",
        ),
    ),
)


def _pdf_text(value: str) -> str:
    safe = value.encode("cp1252", "replace").decode("cp1252")
    return safe.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_demo_pdf(fixture: DemoDocument) -> bytes:
    """Build a small deterministic text PDF without a new runtime dependency."""
    commands = ["BT", "/F1 12 Tf", "50 790 Td"]
    for index, line in enumerate(fixture.lines):
        if index:
            commands.append("0 -24 Td")
        commands.append(f"({_pdf_text(line)}) Tj")
    commands.append("ET")
    stream = "\n".join(commands).encode("cp1252")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length "
        + str(len(stream)).encode("ascii")
        + b" >>\nstream\n"
        + stream
        + b"\nendstream",
    ]
    output = bytearray(b"%PDF-1.4\n%Demo synthetic records\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode("ascii"))
        output.extend(body)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(output)


def fixture_bytes(fixture: DemoDocument) -> bytes:
    return build_demo_pdf(fixture)


def fixture_checksum(fixture: DemoDocument) -> str:
    return hashlib.sha256(fixture_bytes(fixture)).hexdigest()


def find_fixture_by_checksum(checksum: str) -> DemoDocument | None:
    return next(
        (fixture for fixture in DEMO_DOCUMENTS if fixture_checksum(fixture) == checksum), None
    )


def fixture_ocr_pages(fixture: DemoDocument) -> list[dict]:
    return [
        {
            "page": 1,
            "lines": [{"text": line, "confidence": 0.99} for line in fixture.lines],
        }
    ]
