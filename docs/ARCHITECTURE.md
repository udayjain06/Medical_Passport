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
- `backend/app/email.py`: console (development only), SMTP, and Resend adapters for email verification and password recovery.
- `backend/app/rate_limit.py` and `malware_scan.py`: in-memory/shared Redis rate limiting and optional local/ClamAV upload scanning.
- `backend/app/crypto_storage.py`, `encrypted_types.py`, and `rotate_keys.py`: versioned Fernet storage and managed key rotation for document bytes, OCR text, and extraction candidates.
- `backend/app/models.py`: UUID-backed account, patient profile, emergency contact, and audit entities.
- `backend/app/routers/`: health, auth, and profile APIs.
- `backend/app/document_storage.py`: private filesystem adapter with profile-scoped directories, generated storage names, and optional Fernet encryption at rest; legacy plaintext blobs remain readable.
- `backend/app/routers/documents.py`: authenticated upload, list/search/filter, details, content retrieval, metadata updates and deletion.
- `backend/app/extraction.py`, `structured_extraction.py`, and `medical_ai.py`: local OCR plus deterministic rule extraction; an optional compatible AI provider is called only after per-document consent and receives name/number-redacted OCR. Provider outages fall back to rules. Suggestions require item-by-item patient review.
- `backend/app/profile_access.py`: server-side profile selection and owner/caregiver/editor/viewer authorization.
- `backend/app/routers/{extraction,timeline,emergency,family,abha}.py`: review, source-linked events with category/source/date/state filters and edit/delete, emergency shares, account access grants and dependent archival, and ABHA status.
- `backend/alembic/`: migrations.
- `backend/tests/`: API and isolation tests using a disposable SQLite database.

## Frontend layout

- `frontend/src/app/`: landing, login, registration, dashboard, and profile routes.
- `frontend/src/lib/api.ts`: typed same-origin API client.
- `frontend/src/lib/session.ts`: server-side session validation for protected routes.
- `frontend/src/lib/i18n.tsx`: small English/Hindi dictionary and a client-set `mp_language` cookie; the root layout uses it for `<html lang>`.

## Data flow and boundaries

Registration creates an account and an initial profile in one transaction. Login issues a short-lived signed session in an HttpOnly, SameSite=Lax cookie. Logout increments the account's session version, invalidating that account's existing cookies. Unsafe API requests must have an allowed `Origin`; CORS is restricted to configured frontend origins. API responses are marked `no-store`.

Signup requires a Terms acceptance and Privacy acknowledgement and stores versioned consent records in the same transaction as account creation. Emergency-share issuance and renewal record explicit emergency-sharing consent. The owner can review consent metadata and withdraw emergency-sharing consent; withdrawal revokes the active links created by that account. Terms and Privacy records are retained for account history and are not individually withdrawable in the UI. `/api/auth/audit-log` returns at most 100 owner-scoped timestamps and action names, without target identifiers or payloads.

Verification and password-recovery action tokens are signed, single-use, stored as hashes, and expire after 24 hours and 30 minutes respectively. Unverified accounts may sign in, but cannot create emergency shares or grant family-profile access. Forgot-password responses do not disclose whether an account exists; a successful reset increments the session version and invalidates existing sessions.

The default rate limiter is process-local; `REDIS_URL` selects a shared Redis limiter. Authentication limits fail closed if Redis is unavailable, while public-emergency lookups fail open. Limits use `client_ip()`: by default it uses the socket address; `TRUSTED_PROXY_COUNT` enables selection from a configured trusted `X-Forwarded-For` chain. Documents use private local filesystem storage outside the frontend tree. Documents, OCR text, and extraction candidates use the versioned Fernet prefix when encryption keys are configured; `DOCUMENT_ENCRYPTION_KEYS` encrypts with its first key and decrypts with every listed key. The legacy single-key setting remains supported, and plaintext legacy rows/blobs remain readable. `python -m app.rotate_keys` rotates stored data. OCR runs locally; configured AI sends OCR text to a configured provider only after explicit per-document consent, with the patient's profile name and long number-like values redacted. Provider name and processing time are stored on the extraction. Emergency shares store token hashes, allow only selected fields, and record successful public views with a coarse IP prefix. Production startup requires HTTPS, key management, PostgreSQL, and ClamAV; backups and external security review remain operational responsibilities.

Unsafe API request bodies are bounded by `REQUEST_MAX_SIZE_BYTES`. API and Next.js responses use security headers, no-store caching, and frame restrictions; the Next.js `frame-src` permits `blob:` for locally generated document previews while `frame-ancestors 'none'` prevents the app from being embedded. Emergency routes have a strict no-referrer policy. Backend request logs are JSON with server-generated request IDs; filters redact client IPs, bearer/action tokens, emergency URL tokens, and sensitive key/value assignments. `/healthz` is a liveness probe and `/readyz` checks the database.

`docker-compose.yml` defines the local/pilot topology: web and API with PostgreSQL, Redis, and ClamAV. The containers run as non-root where applicable; uploads persist in a dedicated volume. `docs/DEPLOYMENT.md` describes secrets, migration ordering, backup/restore validation, and incident handling. Docker/Compose and PostgreSQL runtime validation must be completed on a Docker-enabled environment before a supervised pilot.

Timeline events may refer to the source document, extraction run, and candidate ID. Filename and checksum snapshots remain after a source document is deleted, while live foreign-key references are nulled. Events can be explicitly marked uncertain or assigned a conflict group; these states preserve ambiguity instead of silently converting it into a confirmed fact.

Emergency share metadata includes an optional label and access-log rows; renewing a link revokes the old token and creates a new token with the same field allowlist. The account API supports JSON export and password-confirmed deletion, including stored document blobs.

Dependent profiles are archived rather than deleted. Archival keeps profile and medical history rows, prevents further selection through the API, revokes active emergency shares, and removes family grants. Archived records need an explicit future recovery workflow before users can access them again.

The frontend build uses Next.js 16's `experimental.cpus: 1` setting because parallel static prerendering intermittently failed to create route-segment directories on the Windows development filesystem. This trades build speed for repeatable local builds; reassess on the production build environment.

The currently installed RapidOCR runtime ships with its default PP-OCR recognition assets and exposes no Hindi script model switch through configuration alone. The UI and transliterated-label rule extraction support Hindi; Hindi-script OCR remains unsupported until a compatible OCR model is deliberately added and validated.

## Planned adapters

ABDM real calls and FHIR exchange remain disabled until official onboarding, specifications, credentials, consent workflows, and validation are available. OCR and candidate review are implemented; no clinical recommendations are generated.
