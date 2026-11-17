# Deployment and operations

This runbook describes a supervised pilot deployment. It does not establish production readiness, regulatory approval, or ABDM certification. Use synthetic data until the operator has completed privacy, security, and legal review.

## Runtime layout

Docker Compose runs the Next.js web app, FastAPI API, PostgreSQL, Redis, and ClamAV. Only the web app and API ports are published by the sample compose file; PostgreSQL, Redis, and ClamAV stay on the private Compose network. Uploaded documents live in the persistent `document_data` volume and are encrypted when `DOCUMENT_ENCRYPTION_KEYS` is configured.

The Compose defaults are for local development. Before a pilot, set `APP_ENV=production`, use HTTPS origins, secure cookies, real email delivery, strong secrets, and a TLS reverse proxy. Never publish the database, Redis, or ClamAV ports to the public internet. Keep the API reachable only from the web service and approved operations network.

## Environment variables

Copy `.env.example` to `.env` and replace every example value. Compose reads this file at the repository root.

| Variable | Required for pilot | Purpose |
| --- | --- | --- |
| `APP_ENV` | `production` | Activates backend production validation. |
| `SECRET_KEY` | Yes | Signs sessions and one-time action tokens. Generate a unique value with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Yes | Compose PostgreSQL database identity. Use a generated password with URL-safe characters because it is included in `DATABASE_URL`. |
| `DATABASE_URL` | Yes | Direct deployments must use `postgresql+psycopg://...`; Compose constructs it from the PostgreSQL variables. |
| `CORS_ORIGINS` | Yes | JSON list of exact HTTPS web origins, for example `["https://passport.example.org"]`. |
| `PUBLIC_APP_URL` | Yes | HTTPS origin used in email links and emergency QR codes. |
| `COOKIE_SECURE` | Yes | Set to `true` behind HTTPS. |
| `DOCUMENT_ENCRYPTION_KEYS` | Yes | JSON array of Fernet keys; the first key encrypts new values and all listed keys decrypt during rotation. |
| `EMAIL_PROVIDER` | Yes | `smtp` or `resend` in production; console delivery is development only. |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_STARTTLS`, `SMTP_USE_SSL`, `EMAIL_FROM` | For SMTP | Configure authenticated TLS delivery. Use either STARTTLS or implicit TLS. |
| `RESEND_API_KEY`, `EMAIL_FROM` | For Resend | Configure the Resend API provider and a verified sender. |
| `REDIS_URL` | Yes | Shared rate-limit store; production startup fails without it. Compose defaults to its internal Redis service. Auth routes fail closed when Redis is unavailable. |
| `MALWARE_SCAN` | `clamav` | Production requires scanning. Compose points the API at the ClamAV service. |
| `CLAMAV_HOST`, `CLAMAV_PORT`, `CLAMAV_TIMEOUT_SECONDS` | Yes | Scanner service address and timeout; Compose supplies the internal host and port. |
| `TRUSTED_PROXY_COUNT` | Yes | Production requires at least one trusted proxy hop appending `X-Forwarded-For`. Compose defaults to `1` because the API is called through Next.js; direct local development can use `0`. |
| `DOCUMENT_PROCESS_RATE_LIMIT_COUNT`, `DOCUMENT_PROCESS_RATE_LIMIT_WINDOW_SECONDS` | Optional | Per-user OCR processing limit; defaults to 10 attempts per 10 minutes. |
| `REQUEST_MAX_SIZE_BYTES`, `DOCUMENT_MAX_SIZE_BYTES` | Optional | Request and file upload limits. |
| `EMERGENCY_MAX_HOURS`, `EMERGENCY_ACCESS_RATE_PER_MINUTE` | Optional | Emergency-share expiry and public endpoint rate limit. |
| `MEDICAL_AI_ENDPOINT`, `MEDICAL_AI_API_KEY`, `MEDICAL_AI_MODEL` | Optional | External extraction provider. Configure only after reviewing patient consent, data handling, and provider terms. |

Generate a Fernet key with:

```sh
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Set it as a JSON array, for example `DOCUMENT_ENCRYPTION_KEYS=["<key>"]`. Store `SECRET_KEY`, encryption keys, database credentials, and mail credentials in a managed secret store. Keep encrypted, access-controlled backups of old encryption keys for the full retention period of data encrypted with them. Do not put secret values in Git, CI logs, issue trackers, or shell history.

### Key rotation

1. Take and verify a database and document-volume backup.
2. Add a newly generated Fernet key at the start of `DOCUMENT_ENCRYPTION_KEYS`, retaining all existing keys after it.
3. Deploy the new key list so new writes use the new first key.
4. Run `docker compose exec api python -m app.rotate_keys` during a quiet maintenance window. The command re-encrypts stored document blobs and extraction data with the first key.
5. Verify the command output and application reads, then take another backup.
6. Remove an old key only after the rotation completed, restored backups were tested, and no retained data still depends on it. Retain a protected recovery copy according to the data-retention policy.

If key rotation is interrupted, keep all old and new keys configured and run the rotation again. Do not discard a key to make a decryption error disappear.

## Start and update

For local Docker validation:

```sh
cp .env.example .env
docker compose config
docker compose up --build
```

Edit `.env` first to set strong local secrets and a Fernet key. The default local Compose profile runs migrations before starting the API. Open `http://localhost:3000`; API liveness and readiness are available at `http://localhost:8010/healthz` and `http://localhost:8010/readyz`.

For a pilot, build and deploy a reviewed image release. Run migrations once as a deployment step before scaling API replicas:

```sh
docker compose build
docker compose run --rm api alembic upgrade head
docker compose up -d --no-build
```

The API service should be private behind the web app and the approved TLS proxy. Do not use sample passwords, console email, HTTP, or empty encryption keys in a pilot. Verify `/readyz`, email verification/reset delivery, upload scanning, and an encrypted document read before enabling real users.

## Reverse proxy and client IP

Set `TRUSTED_PROXY_COUNT` to the number of trusted proxies that append `X-Forwarded-For` before the request reaches the API. Production requires at least one verified hop, and the API must not be directly reachable from untrusted clients. With the supplied topology, the API trusts only the Next.js hop (`1`). If a load balancer sits in front of Next.js, ensure Next.js itself overwrites/appends the client chain safely; do not blindly increase the API trust count. Local direct development may use `TRUSTED_PROXY_COUNT=0` so the socket peer IP is used. Request logs intentionally store request IDs and routes but never full IP addresses, credentials, tokens, or document contents.

## Migrations

Back up PostgreSQL before every schema change. Review the migration file, apply `alembic upgrade head` once before starting new replicas, and run `alembic check` in CI. Do not downgrade a production database as a routine rollback; deploy a forward fix or restore a verified backup into an isolated recovery environment first.

## Backups and restore test

For the operator checklist, including coordinated database, document-volume, and key backups, see [the backup runbook](../scripts/backup.md).

Back up PostgreSQL and the `document_data` volume together. A database-only snapshot is insufficient because document metadata refers to encrypted files in that volume. Quiesce writes or use a coordinated volume/database snapshot so the two copies describe the same point in time. Store backups and the corresponding encryption-key version separately under access control. Never place backup files in the web root or a public bucket.

Example PostgreSQL backup:

```sh
docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > medical-passport.dump
```

Back up the named `document_data` Docker volume with the organization’s volume-snapshot tooling. If using a tar archive, mount that volume read-only into a trusted backup job and write the archive to an encrypted destination. Record the deployment revision and key-set identifier with the backup, never the keys themselves.

At least once before a pilot and on the organization’s schedule thereafter, restore both snapshots to an isolated network with outbound mail and public access disabled. Apply no schema changes until the restored database and volume are paired. Verify migrations, `/readyz`, profile and timeline metadata, and read/decrypt a designated synthetic document. Record the recovery time and outcome; then destroy the isolated copy according to the retention policy.

## Incident checklist

1. Contain access: disable the affected account or service, rotate exposed credentials, and restrict the API/operations network as appropriate.
2. Preserve request IDs, timestamps, deployment revision, and relevant system logs. Do not copy tokens, passwords, full IP addresses, or document contents into incident notes.
3. Revoke exposed emergency shares and invalidate sessions by changing affected credentials/session state.
4. If an encryption key may be exposed, create a new key, prepend it, rotate stored data, and retain the old key only in protected recovery storage until affected backups expire.
5. Assess which accounts and data may be affected with the authorized privacy/security owner. Follow applicable legal and contractual notification requirements after review.
6. Restore only from a verified backup into a controlled environment; test the recovery path before returning service.
7. Document actions, approvals, scope, user impact, and follow-up fixes without including patient data or secrets.
