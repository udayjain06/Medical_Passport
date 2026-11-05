# Roadmap

| Phase | Scope | Status |
|---|---|---|
| 0 | Repository foundation, docs, app shell, FastAPI, environment config, database and migrations, health checks | Complete and verified |
| 1 | Authentication, protected routes, patient profile, validation, persistence | Complete and verified |
| 2 | Private medical document vault, validation, preview, ownership, storage adapter | Implemented; local verification complete |
| 3 | OCR/extraction adapters, structured candidate facts, confidence, review and correction | Local image/PDF OCR and source-text review tested; optional AI provider adapter implemented but externally blocked until configured |
| 4 | Source-linked chronological timeline and verification states | Implemented with category/source/date/state filters, editing/deletion, candidate references, conflict groups, uncertainty notes, and retained source snapshots |
| 5 | Consent-controlled emergency QR with hashed token, expiry, revocation, access logs | Complete and end-to-end tested in a separate browser context |
| 6 | Family profiles and explicit dependent authorization | Dependent profiles, existing-account sharing, role-based switching, document read/write permissions, archival with history retention, and QR/grant revocation implemented and tested; legal authority remains an attestation |
| 7 | Security hardening, multi-worker rate limiting, end-to-end tests, pilot preparation | Planned |
| 8 | ABHA/ABDM adapter after official docs, credentials, authorization, and approvals | Status UI and disabled connector are tested; live integration is externally blocked. ABDM describes sandbox-based ABHA API integration in its [official integration challenge material](https://abdm.gov.in/hackathon) |

Local OCR, source-linked review, timeline filters/editing/deletion, emergency QR, expiry/revocation, field selection, family document permissions, and dependent archival have automated backend and browser coverage. Structured AI candidate generation is disabled until an authorized compatible provider and credentials are configured; local OCR remains functional without it. ABHA/ABDM is externally blocked pending official sandbox access, credentials, approvals, and verified API workflows. The user-provided dependent-authority checkbox is an attestation and does not establish legal authority. Production security controls remain incomplete.
