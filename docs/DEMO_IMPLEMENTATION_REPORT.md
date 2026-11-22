# Local demo implementation report

**Result:** The synthetic demo is implemented and verified in the existing local application. The development app is running at `http://localhost:3000`; its same-origin API proxy targets `http://127.0.0.1:8011`. Demo login: `demo@medicalpassport.local`.

The demo uses the configured local SQLite database and private upload directory. It does not use a separate frontend, backend, database, or external email/AI provider. No Git push or deployment was performed.

## Feature audit

| Feature | Status | Verification and limits |
|---|---|---|
| Signup/login and Explore Demo entry points | **DONE — VERIFIED** | Signup retains its normal registration form and consent requirements. Login and landing page offer Explore Demo. One click calls the real demo-login endpoint and navigates to the dashboard. |
| Demo authentication | **DONE — VERIFIED** | Reserved verified demo user only; existing HttpOnly session cookie, Origin middleware, and rate limiter are used. No user ID/email is accepted from the request. Production rejects `DEMO_MODE=true` and the endpoint is unavailable there. |
| Synthetic Aarav Mehta profile | **DONE — VERIFIED** | Fictional demographics, patient-reported pollen allergy and history, historical Cetirizine entry, fictional Riya contact, and Ira dependent. Persistent banner says the data is synthetic and not for clinical use. |
| Seed records and private documents | **DONE — VERIFIED** | Five deterministic PDFs are written by the existing private-storage adapter, have database metadata and checksums, and contain the synthetic-document disclaimer. Browser flow uploaded and previewed a synthetic PDF; one E2E upload is retained in the demo vault. |
| OCR and extraction review | **DONE — VERIFIED WITH A LABELLED FALLBACK** | Existing local OCR remains available. The known-fixture fallback was tested with OCR forced to fail; it copies only fixture text, labels the result `DEMO EXTRACTION SIMULATION`, leaves candidates pending, and is limited to exact fixture checksums on demo accounts. No external AI was called. Live RapidOCR success on the generated demo PDFs was not established. |
| Fact review and timeline | **DONE — VERIFIED** | Demo browser flow accepted the historical medication candidate, rejected the patient-name candidate, confirmed only the accepted fact, and saw the source-linked timeline. Seeded patient-reported items remain distinct from the previously reviewed source-linked diagnosis. |
| Emergency QR, public access, field consent, and revocation | **DONE — VERIFIED** | The browser generated a backend QR, opened its public URL in a separate unauthenticated browser context, checked the synthetic warning and selected-field scope, opened access history, revoked the link, and verified public access became unavailable. The two QA-created links remain revoked in the demo audit history. |
| Family profile and switching | **DONE — VERIFIED** | Ira’s dependent profile is seeded and the browser switched to it and back. Existing backend tests and the broader browser regression exercise server-side family role enforcement and viewer restrictions. |
| Consent, audit, and FHIR export | **DONE — VERIFIED** | Data & privacy loaded consent and audit history; the actual FHIR R4-aligned export downloaded. No ABDM/NHCX conformance is claimed. |
| Hindi language preference | **DONE — VERIFIED** | The browser switched languages, reloaded, and confirmed the selected language persisted. |
| Normal user registration and login | **DONE — VERIFIED** | The existing registration, email test-hook verification/reset, login, and profile persistence browser regression passed. The temporary E2E family account was removed with the authenticated account-deletion API afterward. |
| Live ABHA/ABDM linking | **BLOCKED EXTERNALLY** | No official sandbox access, credentials, or approval was available for a live request. The app does not claim a connected state or fabricate success. |
| Live third-party email or AI | **NOT USED** | Neither is needed for the local demo. Demo extraction always uses offline rules; real email/AI provider behavior was not part of this verification. |

## Data preservation and repeatability

Before migration/seeding, a SQLite backup was made in the system temporary directory and migration/seeding were tested on a separate database clone with temporary document storage. The clone upgraded to head, passed `alembic check`, and produced the expected idempotent first and second seed results.

On the configured database, every pre-existing primary-key row remained present after migration, seeding, E2E, and cleanup:

| Table | Before | Original rows retained | Final total |
|---|---:|---:|---:|
| Users | 42 | 42 | 43 |
| Patient profiles | 62 | 62 | 64 |
| Medical documents | 35 | 35 | 41 |
| Timeline events | 20 | 20 | 24 |
| Emergency shares | 20 | 20 | 23 |

The additional rows belong to the demo or synthetic browser journey. The seed was run repeatedly; after the first run it created no duplicate core demo records. One duplicate E2E upload was removed through the authenticated document API, leaving one synthetic upload example. No existing non-demo account or record was deleted or overwritten.

## Files added or changed

Added:

- `.env.demo.example`
- `backend/alembic/versions/c4518d2a73f0_add_demo_account_marker.py`
- `backend/app/demo_fixtures.py`, `backend/app/demo_seed.py`
- `backend/tests/test_demo.py`
- `frontend/src/components/demo-login-action.tsx`
- `frontend/tests/e2e/demo.spec.ts`
- `scripts/seed_demo.py`, `scripts/start-demo.ps1`
- `docs/DEMO_IMPLEMENTATION_REPORT.md`

Changed:

- `.env.example`, `.gitignore`
- `backend/app/config.py`, `backend/app/models.py`, `backend/app/schemas.py`
- `backend/app/routers/auth.py`, `backend/app/routers/emergency.py`, `backend/app/routers/extraction.py`
- `frontend/src/app/page.tsx`, `frontend/src/app/globals.css`, `frontend/src/app/(account)/layout.tsx`, `frontend/src/app/emergency/[token]/page.tsx`
- `frontend/src/components/auth-form.tsx`, `frontend/src/components/extraction-review.tsx`, `frontend/src/lib/session.ts`
- `README.md`, `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, `PROJECT_LOG.md`
- Ignored local `frontend/.env.local`: changed only `API_ORIGIN` from the occupied legacy listener at 8010 to the verified demo API at 8011; all other lines were preserved.
- The pre-existing unidentified listener on port 8010 was left running because its process identity could not be verified as belonging to this project. The demo uses 8011 and does not depend on stopping that listener.

Previously untracked verification logs and screenshot artifacts were left untouched.

## Commands and results

- Clone-only validation: `alembic upgrade head`, `alembic check`, `python ..\scripts\seed_demo.py` twice — **passed**, second seed created no duplicate core records.
- Configured SQLite: `alembic upgrade head`, `alembic check` — **passed**, no schema drift; revision `c4518d2a73f0`.
- Backend: `ruff format --check app tests alembic` — **passed**; `ruff check app tests alembic` — **passed**; `pytest -q` — **91 passed**, one existing Starlette/httpx deprecation warning.
- Frontend: `npm run typecheck` — **passed**; `npm run lint` — **passed with one existing warning** (`frontend/public/offline-card.js`, unused `unlockedCard`); `npm run build` — **passed**.
- Dependencies: `npm ls --depth=0` — all declared packages present; two pre-existing extraneous optional WASM packages (`@emnapi/runtime`, `@img/sharp-wasm32`) are reported.
- Browser: `npm run test:e2e -- --trace off --reporter=line --workers=1` — **2 passed** in 59.6 seconds, including the demo journey and the existing registration/OCR/timeline/QR/family/privacy regression. The email test hook was enabled only in a temporary `APP_ENV=test` backend process, then the development app was restored.
- `git diff --check` — passed on the final tracked diff; no whitespace errors.
- `scripts/start-demo.ps1` — PowerShell parser check passed. Its backend shutdown guard verifies the project path, Uvicorn command, ASGI target, and requested port before stopping a process.

## Remaining limits

- This run verified SQLite; a PostgreSQL service was not run here.
- The generated demo PDFs were previewed and reviewed. The exact-fixture OCR-failure fallback is tested, but successful live OCR on those PDFs was not established.
- Real phone/LAN scanning, physical Android/iOS accessibility, and external email or AI delivery were not exercised.
- ABHA/ABDM remains externally blocked pending official sandbox access, credentials, and approvals. This demo is not production-ready, clinically validated, or an ABDM-certified product.
