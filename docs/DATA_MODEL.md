# Data Model

## Implemented tables

| Table | Purpose | Important constraints |
|---|---|---|
| `users` | Login identity and session version | UUID primary key; normalized email unique; password hash only |
| `patient_profiles` | A primary or dependent patient-reported profile owned by an account | UUID primary key; indexed `user_id` foreign key; dependent profiles can be archived with `archived_at`; cascade on account deletion |
| `emergency_contacts` | Contact rows belonging to one profile | UUID primary key; profile foreign key; cascade delete |
| `audit_events` | Minimal records of successful security/profile/document actions | UUID primary key; nullable user foreign key; indexed by user/time |
| `medical_documents` | Private document metadata owned by one patient profile and uploader | UUID primary key; profile/user foreign keys; generated unique storage key; indexed by profile/time |
| `document_extractions` | OCR/candidates awaiting review, scoped to source document/profile | Status, OCR text, candidate JSON, engine version; cascades with source document |
| `timeline_events` | Patient-entered and patient-confirmed source-linked history | Profile foreign key; optional document, extraction, and candidate references; source filename/checksum snapshots; provenance, verification, conflict group, uncertainty note |
| `emergency_shares` | Opaque, expiring, revocable emergency shares | Hashed token only; selected field allowlist; optional label; profile foreign key |
| `emergency_access_logs` | Successful public emergency-link views | Share foreign key with cascade; timestamp; coarse IP prefix only; truncated user-agent |
| `profile_access` | Role grants for account-to-account profile access | Unique profile/user pair; owner-granted caregiver/editor/viewer role |

All tables have UTC timestamps. Profile values are patient-entered in this phase. The API returns `verification_status: patient_reported`; an empty allergy or medication value is not normalized to “none.” PostgreSQL uses native UUIDs through SQLAlchemy's portable `Uuid` type; SQLite is used for local development and tests.

Revisions `1759d0b09e17`, `d8f9141748e7`, `83848f3217a1`, `4340458f304b`, `6fafbd8b528d`, `9a7c2d41b6e0`, and `b1c4e7a90d25` add the account/profile schema, documents, extraction/timeline/emergency shares, profile access, dependent profiles, archival, durable timeline source references, emergency share labels, and emergency access logs. The latest migration backfills document snapshots and matching extraction/candidate IDs where the prior data supports an unambiguous match. File bytes live in private local storage and are never stored in the database. Blobs are encrypted with Fernet when configured; production requires a valid key. Legacy plaintext blobs remain readable. Exports include profile, timeline, document metadata, and emergency-link metadata, but not file bytes or secret QR tokens.

SQLite connections enable `PRAGMA foreign_keys=ON`; automated tests cover invalid references, valid references, cascades, and zero foreign-key violations. PostgreSQL remains the production database target.

## Implemented profile fields

Full name, date of birth, blood group, phone number, known allergies, major conditions, current medications, and up to five emergency contacts. The web form currently manages one primary emergency contact, while the API/model support multiple contacts.

## Family and integration status

Dependent profile rows and account-to-account access grants are implemented. Archiving a dependent keeps medical records and provenance, blocks profile access, revokes emergency shares, and removes sharing grants. The authority confirmation is stored as the caregiver's attestation; the application does not validate legal authority. ABHA linking and FHIR exchange are not implemented because official sandbox access, credentials, authorized workflows, and validation are unavailable. The official ABDM site describes sandbox-based ABHA API integration in its [integration challenge material](https://abdm.gov.in/hackathon).
