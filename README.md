# Medical Passport

Medical Passport is a private, source-linked personal health record for India. It complements the ABHA/ABDM ecosystem and does not replace it. The application includes the Phase 0/1 account and profile foundation, a protected document vault, local OCR and human review, a source-linked timeline, emergency QR sharing, and family access controls.

The app includes registration, patient profiles, a private document vault, local OCR with human review, source-linked timeline events, expiring emergency QR shares, and account-to-account family access grants. Optional structured AI suggestions require an explicitly configured approved provider. Live ABHA/ABDM exchange is disabled pending sandbox onboarding and credentials. Email verification and password recovery are not active because no delivery provider is configured.

## Requirements

- Node.js 20.9 or newer and npm
- Python 3.11 or newer
- Git
- PostgreSQL for production. Local development defaults to SQLite so the app can run without Docker.

## Run locally

1. From the repository root, copy `.env.example` to `backend/.env` and replace `SECRET_KEY` with a generated value. PowerShell:

   ```powershell
   Copy-Item .env.example backend/.env
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   # Paste the generated value into backend/.env as SECRET_KEY.
   ```

2. Create the backend environment, install its dependencies, and apply migrations:

   ```powershell
   cd backend
   py -3 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   pip install -r requirements-dev.txt
   alembic upgrade head
   uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
   ```

The API docs are available at `http://127.0.0.1:8010/docs`; liveness and readiness checks are `/api/health/live` and `/api/health/ready`. Uploaded files default to `backend/private_uploads` (outside the frontend public directory); configure `DOCUMENT_STORAGE_PATH` and `DOCUMENT_MAX_SIZE_BYTES` in `backend/.env` as needed. The default limit is 10 MiB. Set `PUBLIC_APP_URL` to the public origin used in emergency QR links. OCR uses local RapidOCR; optional AI candidate extraction is disabled unless `MEDICAL_AI_ENDPOINT`, `MEDICAL_AI_API_KEY`, and `MEDICAL_AI_MODEL` are configured. OCR text will then be sent to that provider.

3. In a second PowerShell window, run the frontend:

   ```powershell
   cd frontend
   npm ci
   Copy-Item .env.local.example .env.local
   npm run dev
   ```

   Open `http://localhost:3000`. The Next.js server proxies `/api/*` to the FastAPI service. Session cookies are HttpOnly and are not stored in browser JavaScript.

### PostgreSQL

Set `DATABASE_URL` in `backend/.env` to a SQLAlchemy URL such as `postgresql+psycopg://medical_passport:change-me@localhost:5432/medical_passport`, then run `alembic upgrade head`. Use a private database, a unique secret, HTTPS, and `COOKIE_SECURE=true` in production. The repository does not claim production readiness or ABDM certification.

## Checks

Run from `backend/` with the virtual environment active:

```powershell
pytest
ruff check .
```

Run from `frontend/`:

```powershell
npm run lint
npm run typecheck
npm run build
```

For the browser journey, install the local Chromium headless shell once with `npm run playwright:install`. Keep the FastAPI service and Next.js development server running in separate terminals, then run `npm run test:e2e` from `frontend/`.

The automated suite covers registration/login and profile persistence, local OCR and candidate review, source-linked timeline filters/edit/delete and conflict/uncertainty states, authorized document preview/deletion, emergency QR field restrictions/revocation/expiry, family document permissions, dependent archival and isolation, and role-based profile access. PDFs and images are signature-checked and served only through authorized endpoints. OCR runs synchronously; there is no durable job queue. Structured AI extraction is disabled until an explicitly configured provider is available. Family access supports dependent profiles and existing accounts; the authority check is a user attestation, not legal verification. Dependent archival retains medical history, blocks access, and revokes active QR shares and profile grants. SQLite enables foreign keys on each connection. This development implementation does not include malware scanning, at-rest encryption, or cloud object storage; use synthetic documents and add those controls before handling real patient records.

For a production build that uses a non-default API origin, set `API_ORIGIN` before `npm run build`; Next.js records the rewrite target during build. Local development defaults to the FastAPI service at `http://127.0.0.1:8010`.

ABHA/ABDM connection status is explicitly shown as externally blocked. The connector does not simulate linking and cannot perform a live workflow without official sandbox/API access, credentials, and required approvals.

## Privacy notes

The Phase 1 profile is patient-entered and is always labelled as patient-reported. Empty allergy or medication fields mean “not recorded,” not “none.” Profile APIs require an authenticated account, enforce same-origin writes, and send `Cache-Control: no-store`. Do not enter real patient information in development. Before real-user launch, obtain appropriate Indian legal, privacy, clinical, and security review.

## Project documents

- [Product specification](docs/PRODUCT_SPEC.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Data model](docs/DATA_MODEL.md)
- [Security and privacy](docs/SECURITY_PRIVACY.md)
- [Roadmap](docs/ROADMAP.md)
- [Architecture decisions](docs/DECISIONS.md)
- [Project log](PROJECT_LOG.md)
