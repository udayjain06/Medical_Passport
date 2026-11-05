# Final local demo report — 2026-11-05

## Status

The local application is running in Chrome at `http://localhost:3000`; its FastAPI service responds on `http://127.0.0.1:8010`. The actual browser journey and automated checks listed below passed. The application is suitable for a local demo with synthetic data. This is not a production release certification.

## Fixed

- The frontend API rewrite fallback in `frontend/next.config.ts` pointed to port 8000, while `frontend/.env.local` and the running backend used port 8010. An origin probe showed that writes through 8000 returned `403 Untrusted request origin`, while the backend on 8010 accepted the trusted frontend origin. Changed the fallback to 8010. The live Next server hot-reloaded it; the same-origin login probe then reached the backend and returned its expected `401` for an unknown account.
- Hardened `frontend/src/components/auth-form.tsx`: forms declare `method="post"`, submit stays disabled until hydration and while busy, and registration/login continue through the real JSON API. The no-JavaScript check verifies the form stays non-submittable before hydration; the final browser flow registered and signed in without a password in the URL.
- Updated README local backend commands and API docs URL to port 8010.

## Verified

- Real-browser Playwright flow against the running Next app: **1 passed (56.6s)**. It covers registration/login, protected dashboard and profile, document upload, OCR/extraction review and confirmation, timeline, emergency field selection and QR/public summary, revocation/access denial, family profile switching and permissions, document preview, ABHA unavailable state, responsive routes, and unexpected network/console/5xx checks. The suite also saved the screenshots linked below.
- Backend: Ruff passed; pytest **21 passed** (one Starlette/httpx deprecation warning); `pip check` found no broken requirements.
- Frontend: lint and TypeScript checks passed; optimized production build passed (13 routes). `npm ls --depth=0` exits successfully and reports two extraneous optional packages: `@emnapi/runtime@1.11.3` and `@img/sharp-wasm32@0.35.5`.
- Database: Alembic current is `9a7c2d41b6e0 (head)`; `alembic check` found no new operations. SQLite integrity check is `ok`; foreign-key check has zero violations.
- Account journey was also opened in the user's actual Chrome window. The browser is left on the signed-in dashboard at `http://localhost:3000/dashboard`.
- The configured SQLite database was backed up with SQLite's online backup API before E2E writes to `C:\Users\Jainu\Documents\Codex\work\medical-passport-local-demo-backups\medical_passport_pre_e2e_a0fe3b9e7bc84ee497a802633154deb1.sqlite`. Backup integrity is `ok`, with 37 users and 31 documents. The current database has 41 users and 35 documents; all 31 original document rows and all 31 original blob files remain present. Current integrity is `ok` and there are zero FK violations. Four synthetic users/documents were added during two authorized full E2E runs; no original data or uploads were deleted.

### Screenshots

- Landing page: [landing.png](demo-screenshots/landing.png)
- Login: [login.png](demo-screenshots/login.png)
- Signed-in dashboard: [dashboard.png](demo-screenshots/dashboard.png)

## Implemented but externally blocked

- AI candidate extraction can use the configured provider integration, but live provider extraction cannot be verified without endpoint/model credentials. Local OCR, structured suggestions, source-linked review and user confirmation were exercised; AI output is not represented as independently verified medical fact.
- ABHA/ABDM settings and unavailable connection state are integrated and tested. Actual official linking remains blocked pending valid official sandbox/production credentials, approvals, and supported access.

## Not tested / remaining limits

- Production deployment, PostgreSQL, multi-worker rate limiting, real email/SMS delivery, malware scanning, and clinical/legal/security certification were not tested in this local verification.
- The npm tree contains the two optional extraneous packages noted above; declared dependencies and all executed frontend commands succeed.
- OS process-owner inspection for ports was unavailable in this session (`Get-CimInstance` reported that CIM access was unavailable; the TCP owner-table call returned access denied). No process was killed or restarted. Port 3000 was visually confirmed to serve this Next.js application, the backend on 8010 answered the configured API, and the Next configuration hot-reloaded successfully.
- No Git commit, remote, push, or deployment was made.

## Files modified for this remediation and report

- `frontend/next.config.ts`
- `frontend/src/components/auth-form.tsx`
- `frontend/tests/e2e/phase1.spec.ts` (adds hydration guard and screenshot capture assertions)
- `README.md`
- `PROJECT_LOG.md`
- `docs/FINAL_LOCAL_DEMO_REPORT.md`

## Commands used

Checks run included backend `ruff check app tests alembic`, `python -m pytest -q -p no:cacheprovider`, `python -m pip check`, `alembic current`, and `alembic check`; frontend `npm run lint`, `npm run typecheck`, `npm run build` with `API_ORIGIN=http://127.0.0.1:8010` and `NEXT_BUILD_DIR=.next-local-demo`, and `npm run test:e2e`. No migration was applied in this final local verification because the configured database was already at head.

## Run locally

Terminal 1:

```powershell
cd D:\miniproject\backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

Terminal 2:

```powershell
cd D:\miniproject\frontend
npm run dev -- --hostname 127.0.0.1 --port 3000
```

Open `http://localhost:3000`. The frontend's `.env.local` should set `API_ORIGIN=http://127.0.0.1:8010`; the backend environment must allow `http://localhost:3000` as a trusted origin.
