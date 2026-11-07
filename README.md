# Medical Passport

Medical Passport is a private, source-linked personal health record for India. It complements the ABHA/ABDM ecosystem and does not replace it. The application includes the Phase 0/1 account and profile foundation, a protected document vault, local OCR and human review, a source-linked timeline, emergency QR sharing, and family access controls.

The app includes registration, patient profiles, a private document vault, local OCR with human review, source-linked timeline events, expiring emergency QR shares, and account-to-account family access grants. An offline rule-based extractor suggests only text present in the document; items stay pending until the patient reviews them. An optional compatible AI provider can add suggestions, with local rules used if that provider is absent or unavailable. Live ABHA/ABDM exchange is disabled pending sandbox onboarding and credentials. Email verification and password recovery are not active because no delivery provider is configured.

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

The API docs are available at `http://127.0.0.1:8010/docs`; liveness and readiness checks are `/api/health/live` and `/api/health/ready`. Uploaded files default to `backend/private_uploads` (outside the frontend public directory); configure `DOCUMENT_STORAGE_PATH` and `DOCUMENT_MAX_SIZE_BYTES` in `backend/.env` as needed. The default limit is 10 MiB. Set `PUBLIC_APP_URL` to the public origin used in emergency QR links. OCR uses local RapidOCR and offline rules. To encrypt new local document blobs at rest, generate a Fernet key with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` and set `DOCUMENT_ENCRYPTION_KEY` in `backend/.env`; keep the key backed up and unchanged, since encrypted files cannot be read without it. A blank key is allowed for local development, and legacy plaintext blobs remain readable. Optional AI extraction requires `MEDICAL_AI_ENDPOINT`, `MEDICAL_AI_API_KEY`, and `MEDICAL_AI_MODEL`; OCR text is sent to that configured provider, and rule extraction is used if the call fails.

3. In a second PowerShell window, run the frontend:

   ```powershell
   cd frontend
   npm ci
   Copy-Item .env.local.example .env.local
   npm run dev
   ```

   Open `http://localhost:3000`. The Next.js server proxies `/api/*` to the FastAPI service. Session cookies are HttpOnly and are not stored in browser JavaScript.

### PostgreSQL

Set `DATABASE_URL` in `backend/.env` to a SQLAlchemy URL such as `postgresql+psycopg://medical_passport:change-me@localhost:5432/medical_passport`, then run `alembic upgrade head`. Production startup requires a valid `DOCUMENT_ENCRYPTION_KEY`, `COOKIE_SECURE=true`, HTTPS `CORS_ORIGINS` and `PUBLIC_APP_URL`, and a PostgreSQL `DATABASE_URL`. Set `TRUSTED_PROXY_COUNT` to the number of trusted proxy hops (default `0` trusts only the socket address; set it only when the app is behind your own proxy chain). Back up the Fernet key in a secrets manager; losing it makes encrypted document blobs unreadable. Accounts can download metadata/profile/timeline exports or permanently delete the account from **Data & privacy**. This project does not claim production readiness or ABDM certification.

## Checks

Run from `backend/` with the virtual environment active:

```powershell
ruff format --check app tests alembic
ruff check app tests alembic
pytest
alembic check
```

Run from `frontend/`:

```powershell
npm run lint
npm run typecheck
npm run build
```

For the browser journey, install the local Chromium headless shell once with `npm run playwright:install`. Keep the FastAPI service and Next.js development server running in separate terminals, then run `npm run test:e2e` from `frontend/`.

The automated suite covers registration/login and profile persistence, local OCR and candidate review, source-linked timeline filters/edit/delete and conflict/uncertainty states, authorized document preview/deletion, emergency QR field restrictions/revocation/expiry/renewal/access history, family document permissions, dependent archival and isolation, role-based profile access, data export and deletion, extraction fallbacks, and encrypted storage. PDFs and images are signature-checked and served only through authorized endpoints. OCR runs synchronously; there is no durable job queue. Rule extraction works offline; configured AI providers receive OCR text and are not required. Family access supports dependent profiles and existing accounts; the authority check is a user attestation, not legal verification. Dependent archival retains medical history, blocks access, and revokes active QR shares and profile grants. SQLite enables foreign keys on each connection. Document blobs use Fernet encryption when a key is configured; production requires it, while local development can run without it. OCR text is not encrypted at rest. Malware scanning and cloud object storage are not included; use synthetic documents and complete privacy/security review before handling real patient records.

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
