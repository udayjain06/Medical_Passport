# Product Specification

## Purpose

Medical Passport turns scattered medical documents into an organized, source-linked history and an emergency-ready summary. It complements ABHA/ABDM and must not claim official integration or certification without authorization and evidence.

## Current delivery

Phase 1 provides account registration and login, a protected dashboard, and a patient-reported profile containing name, date of birth, blood group, contact, known allergies, major conditions, current medications, and emergency contacts. A blank value means the information has not been recorded. It is not evidence that the patient has no allergy or condition.

Current code includes a document vault with local OCR and human review, source-linked patient-confirmed timeline events, expiring consent-based emergency QR shares, dependent profiles, and role-based access grants to existing user profiles. Structured AI extraction is only available with an explicitly configured provider. Dependent authority is an attestation rather than a verified legal status. Live ABHA/ABDM exchange is externally blocked; the UI must state these limits and never simulate success.

## Product principles

- Keep every medical fact attributable to a user, a source, and a verification state.
- Do not invent medical details, diagnoses, medication instructions, or successful integrations.
- Keep AI suggestions unverified until a person reviews them.
- Keep public sharing minimal, explicit, expiring, and revocable.
- Build for accessible, calm, mobile-friendly use and clear error states.
