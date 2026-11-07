# Security and Privacy

## Phase 1 controls

- Argon2 password hashing through `pwdlib`; plaintext passwords are never persisted.
- Signed HS256 sessions use an HttpOnly, SameSite=Lax cookie with a configurable lifetime. Logout increments `session_version`, revoking existing sessions for the account.
- All profile reads and writes require authentication and are scoped to the authenticated user. Writes reject an absent or unapproved `Origin`.
- CORS origins are explicit configuration. The Next.js server proxies API traffic so the browser uses a same-origin route.
- Registration and login have in-process IP rate limits. Request validation responses omit submitted input. API responses use `Cache-Control: no-store`.
- Audit rows record successful account/profile actions without storing request bodies or medical values.
- Production configuration rejects a short/default secret and requires secure cookies, HTTPS CORS/public origins, PostgreSQL, and a valid Fernet document key.
- Authentication rate limits use the socket IP by default. `TRUSTED_PROXY_COUNT` opts into the configured trusted proxy chain; do not enable it when requests can bypass those proxies.

## Phase 2 document controls

- Every document endpoint requires the existing authenticated session. After `resolve_profile` verifies ownership or a current grant, reads are scoped to the selected profile. Uploader ID is audit metadata and does not hide a record from an authorized viewer/caregiver; inaccessible IDs return 404.
- Uploads are streamed with a configurable 10 MiB cap, validated against PDF/JPEG/PNG signatures and matching MIME type, and stored with generated UUID names under a private directory outside `frontend/public`.
- Storage paths are derived from UUIDs and checked to remain beneath the configured root. No public URLs or storage credentials are exposed. Content responses are authorized, private/no-store, and use `nosniff`.
- Document blobs use Fernet encryption at rest when `DOCUMENT_ENCRYPTION_KEY` is configured. Production refuses to start without a valid key; legacy plaintext blobs remain readable. Losing or rotating the key without re-encrypting stored blobs makes them unreadable. OCR text and database backups are not encrypted by this application.
- Emergency links use random bearer tokens; only SHA-256 hashes are stored. Access is rate-limited, audited, field-allowlisted, expiry-checked, revocable, renewable by token rotation, and marked `noindex`. Successful views record a coarse IP prefix and truncated user-agent. Anyone holding an active link can see its selected fields until expiry/revocation.
- Family account access is checked against `profile_access` on every API request. Viewers cannot modify profiles, upload/delete documents, create shares, or edit events. Access grants require the other account to exist.
- Family document tests cover owner, caregiver, viewer read access, viewer write denial, unauthorized accounts, and cross-profile isolation.
- Dependent profiles can be archived only by their owning account; the primary profile cannot be archived. Archival retains history, blocks further API selection, revokes active emergency shares, and removes sharing grants.
- Timeline references include extraction/candidate IDs when known plus filename/checksum snapshots. Deleting a source document nulls the live foreign keys while retaining provenance. Timeline filters, edit/delete authorization, conflict groups, and uncertainty notes are server-enforced.
- SQLite foreign-key enforcement is enabled on every SQLAlchemy SQLite connection and tested for valid, invalid, and cascading references.
- Local OCR runs on the application server. If an AI endpoint, API key, and model are configured, OCR text is transmitted to that provider for structured candidate extraction. Configure only a provider approved for this health data; no AI provider is enabled by default.

## Limits and launch requirements

The development cookie defaults to `Secure=false` for localhost only. The in-memory rate limiter does not coordinate multiple workers. No email/phone verification or password recovery provider is configured. SQLite is a local convenience; production needs PostgreSQL, encrypted backups, TLS, managed secrets, monitoring, and tested restore procedures. Malware scanning, durable OCR job processing, cloud object storage, audit review tooling, and external security testing are not implemented. OCR text is not encrypted at rest. Account export omits file bytes and QR bearer tokens; account deletion requires the password and removes uploaded blobs and owned data. Dependent authority is based on a user attestation and is not independently verified.

Use synthetic records during development. Before a real-user launch, obtain appropriate Indian legal, privacy, clinical, and security review. Do not represent the product as ABDM certified or clinically validated.
