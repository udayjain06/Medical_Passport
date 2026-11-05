# Architecture

## Current system

```text
Browser
  └─ Next.js App Router (React, TypeScript, Tailwind)
       ├─ server-side protected route check ── FastAPI /api/auth/me
       └─ same-origin /api/* rewrite ───────── FastAPI
                                               ├─ Pydantic validation
                                               ├─ HttpOnly signed session cookie
                                               ├─ SQLAlchemy 2.x
                                               └─ SQLite (local) / PostgreSQL (configured)
```

The frontend does not hold session tokens in JavaScript. FastAPI validates every protected request and resolves the active patient profile through account ownership or an explicit access grant. Document visibility is profile-scoped, while write operations additionally check role permissions. Archived profiles cannot be selected. Alembic owns schema changes; the application does not create production tables at startup. `/api/health/live` reports process health and `/api/health/ready` checks database connectivity.

## Backend layout

- `backend/app/config.py`: environment-backed settings and production checks.
- `backend/app/database.py`: SQLAlchemy engine, session factory, and declarative base; SQLite connection hooks enable foreign-key enforcement on every connection.
- `backend/app/models.py`: UUID-backed account, patient profile, emergency contact, and audit entities.
- `backend/app/routers/`: health, auth, and profile APIs.
- `backend/app/document_storage.py`: private filesystem adapter with profile-scoped directories and generated storage names; replaceable with an S3-compatible adapter later.
- `backend/app/routers/documents.py`: authenticated upload, list/search/filter, details, content retrieval, metadata updates and deletion.
- `backend/app/extraction.py` and `medical_ai.py`: on-device OCR for images/scanned PDFs, plus optional configured OpenAI-compatible structured extraction. Suggestions require user review.
- `backend/app/profile_access.py`: server-side profile selection and owner/caregiver/editor/viewer authorization.
- `backend/app/routers/{extraction,timeline,emergency,family,abha}.py`: review, source-linked events with category/source/date/state filters and edit/delete, emergency shares, account access grants and dependent archival, and ABHA status.
- `backend/alembic/`: migrations.
- `backend/tests/`: API and isolation tests using a disposable SQLite database.

## Frontend layout

- `frontend/src/app/`: landing, login, registration, dashboard, and profile routes.
- `frontend/src/lib/api.ts`: typed same-origin API client.
- `frontend/src/lib/session.ts`: server-side session validation for protected routes.

## Data flow and boundaries

Registration creates an account and an initial profile in one transaction. Login issues a short-lived signed session in an HttpOnly, SameSite=Lax cookie. Logout increments the account's session version, invalidating that account's existing cookies. Unsafe API requests must have an allowed `Origin`; CORS is restricted to configured frontend origins. API responses are marked `no-store`.

The local rate limiter is process-local and is suitable only for a single development worker. Documents currently use private local filesystem storage outside the frontend tree. OCR runs locally; configured AI sends OCR text to the configured provider and is disabled unless endpoint, key, and model are supplied. Production deployment must provide shared rate limiting, HTTPS, strong secret management, PostgreSQL backups, private object storage, operational monitoring, and security review. No malware scanning or at-rest encryption layer is implemented or claimed.

Timeline events may refer to the source document, extraction run, and candidate ID. Filename and checksum snapshots remain after a source document is deleted, while live foreign-key references are nulled. Events can be explicitly marked uncertain or assigned a conflict group; these states preserve ambiguity instead of silently converting it into a confirmed fact.

Dependent profiles are archived rather than deleted. Archival keeps profile and medical history rows, prevents further selection through the API, revokes active emergency shares, and removes family grants. Archived records need an explicit future recovery workflow before users can access them again.

The frontend build uses Next.js 16's `experimental.cpus: 1` setting because parallel static prerendering intermittently failed to create route-segment directories on the Windows development filesystem. This trades build speed for repeatable local builds; reassess on the production build environment.

## Planned adapters

ABDM real calls and FHIR exchange remain disabled until official onboarding, specifications, credentials, consent workflows, and validation are available. OCR and candidate review are implemented; no clinical recommendations are generated.
