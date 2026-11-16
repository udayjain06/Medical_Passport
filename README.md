# Medical Passport

Medical Passport is a private, source-linked personal health record for India. It complements the ABHA/ABDM ecosystem and does not replace it. The application includes the Phase 0/1 account and profile foundation, a protected document vault, local OCR and human review, a source-linked timeline, emergency QR sharing, and family access controls.

The app includes registration, patient profiles, a private document vault, local OCR with human review, source-linked timeline events, expiring emergency QR shares, and account-to-account family access grants. An offline rule-based extractor suggests only text present in the document; items stay pending until the patient reviews them. An optional compatible AI provider can add suggestions, with local rules used if that provider is absent or unavailable. Live ABHA/ABDM exchange is disabled pending sandbox onboarding and credentials. New accounts can sign in before email verification, but emergency-link creation and family profile grants stay locked until verification. Password resets use single-use links and invalidate existing sessions.

## Requirements

- Node.js 20.9 or newer and npm
- Python 3.11 or newer
- Git
- PostgreSQL for production. Local development defaults to SQLite so the app can run without Docker.
- Docker Desktop with Compose v2 for the optional container stack.

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

The API docs are available at `http://127.0.0.1:8010/docs`; liveness and readiness checks are `/api/health/live` and `/api/health/ready`, with `/healthz` and `/readyz` aliases. Uploaded files default to `backend/private_uploads` (outside the frontend public directory); configure `DOCUMENT_STORAGE_PATH` and `DOCUMENT_MAX_SIZE_BYTES` in `backend/.env` as needed. The per-document limit is 10 MiB and the overall request body limit is 12 MiB. Set `PUBLIC_APP_URL` to the public origin used in emergency QR links. OCR uses local RapidOCR and offline rules. To encrypt documents, OCR text, and extraction candidates at rest, generate a Fernet key with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` and set `DOCUMENT_ENCRYPTION_KEYS=["<generated-key>"]` in `backend/.env`; the first key encrypts and the ordered list supports decrypting old keys during rotation. The legacy `DOCUMENT_ENCRYPTION_KEY` setting remains readable. A blank key is allowed only for local development; legacy plaintext files and extraction rows remain readable. Optional AI extraction requires `MEDICAL_AI_ENDPOINT`, `MEDICAL_AI_API_KEY`, and `MEDICAL_AI_MODEL`; OCR text is sent to that configured provider, and rule extraction is used if the call fails.

### Optional Docker Compose stack

The Compose stack runs the web app, FastAPI, PostgreSQL, Redis, and ClamAV. It binds the web/API ports to loopback by default and keeps database, Redis, and scanner ports private. In PowerShell from the repository root:

```powershell
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Paste the generated values into .env as SECRET_KEY and DOCUMENT_ENCRYPTION_KEYS=["<key>"].
docker compose config
docker compose up --build
```

Open `http://localhost:3000`. ClamAV downloads its signature database during startup, so first startup can take a few minutes. The Compose defaults are for local development only; do not use the example secrets or console email for a pilot. For a supervised pilot, set production HTTPS origins, `COOKIE_SECURE=true`, SMTP or Resend delivery, a unique PostgreSQL password, and encryption keys, then follow [the deployment runbook](docs/DEPLOYMENT.md). Docker image builds and the Compose stack must be run on a machine with Docker installed.

Email verification uses signed one-time links that expire after 24 hours; password reset links expire after 30 minutes. The local default `EMAIL_PROVIDER=console` prints only a masked recipient and redacted subject/body; it intentionally does not expose links. Configure SMTP or Resend in `backend/.env` to receive usable links. Production startup rejects console delivery and plaintext SMTP. The authenticated email-link test hook requires both `APP_ENV=test` and `EMAIL_TEST_HOOK_ENABLED=true`; production startup rejects that flag. Forgot-password responses are the same whether an account exists or not, and reset invalidates every existing session.

3. In a second PowerShell window, run the frontend:

   ```powershell
   cd frontend
   npm ci
   Copy-Item .env.local.example .env.local
   npm run dev
   ```

   Open `http://localhost:3000`. The Next.js server proxies `/api/*` to the FastAPI service. Session cookies are HttpOnly and are not stored in browser JavaScript.

### PostgreSQL

Set `DATABASE_URL` in `backend/.env` to a SQLAlchemy URL such as `postgresql+psycopg://medical_passport:change-me@localhost:5432/medical_passport`, then run `alembic upgrade head`. Production startup requires at least one valid `DOCUMENT_ENCRYPTION_KEYS` value (or the legacy single-key variable), `COOKIE_SECURE=true`, HTTPS `CORS_ORIGINS` and `PUBLIC_APP_URL`, a PostgreSQL `DATABASE_URL`, and `MALWARE_SCAN=clamav`. Set `TRUSTED_PROXY_COUNT` to the number of trusted proxy hops (default `0` trusts only the socket address; set it only when the app is behind your own proxy chain). Back up the database, private upload directory, and all active Fernet keys; losing every key makes encrypted medical data unreadable. Accounts can download metadata/profile/timeline exports or permanently delete the account from **Data & privacy**. Rate limiting uses in-memory counters by default; setting `REDIS_URL` selects a shared Redis counter. Authentication limits fail closed if Redis is unavailable, while public emergency lookups fail open so a Redis outage does not block emergency access. This project does not claim production readiness or ABDM certification.

#### Encryption key rotation

Back up the database, private uploads, and current keys before rotating. Generate a new Fernet key, then configure `DOCUMENT_ENCRYPTION_KEYS` as a JSON list with the new key first and every old decryption key after it, for example `DOCUMENT_ENCRYPTION_KEYS=["NEW_KEY","OLD_KEY"]`. From `backend/`, run `python -m app.rotate_keys`; the command re-encrypts document blobs, OCR text, and candidate records with the first key and prints aggregate counts only. Keep all keys configured if it fails. After a successful run and restore test, redeploy with only the new key. Do not remove the old key until rotation and backups have been verified.

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

For the browser journey, install the local Chromium headless shell once with `npm run playwright:install`. Use a disposable database and enable the authenticated email-link hook only in the isolated test backend. In a backend PowerShell window, set `APP_ENV=test`, `EMAIL_TEST_HOOK_ENABLED=true`, `DATABASE_URL` to a temporary SQLite file, `PUBLIC_APP_URL` to the frontend test origin, and `CORS_ORIGINS` to that same origin; then apply migrations and start Uvicorn. In another window, start Next.js and run `npm run test:e2e` from `frontend/`. The test hook keeps verification/reset links in process memory and is rejected by production settings; never enable it on a shared or production service.

The automated suite covers registration/login and profile persistence, local OCR and candidate review, source-linked timeline filters/edit/delete and conflict/uncertainty states, authorized document preview/deletion, emergency QR field restrictions/revocation/expiry/renewal/access history, family document permissions, dependent archival and isolation, role-based profile access, data export and deletion, extraction fallbacks, and encrypted storage. PDFs and images are signature-checked and served only through authorized endpoints. OCR runs synchronously; there is no durable job queue. Rule extraction works offline; configured AI providers receive OCR text and are not required. Family access supports dependent profiles and existing accounts; the authority check is a user attestation, not legal verification. Dependent archival retains medical history, blocks access, and revokes active QR shares and profile grants. SQLite enables foreign keys on each connection. Documents, OCR text, and candidates use Fernet encryption when keys are configured; production requires keys, while local development may run without them. Production requires MALWARE_SCAN=clamav; uploads are streamed to ClamAV before persistence, and scanner outages reject uploads. Local development defaults to MALWARE_SCAN=off. Cloud object storage is not included; use synthetic documents and complete privacy/security review before handling real patient records.

The security/operations suite also covers email-provider redaction and failure handling, verification/reset token expiry and replay, password-reset session invalidation, generic forgot-password responses, unverified-user restrictions, Redis failure modes, EICAR rejection and scanner outages, encryption-key rotation, request-size limits, security headers, and structured-log redaction. `docker compose config` and container image builds require Docker Compose v2.

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
