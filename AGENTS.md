# Medical Passport contributor guidance

- Preserve the documented phase sequence and inspect `PROJECT_LOG.md` before continuing work.
- Keep health information private, tenant-scoped, and source-linked. Never use real patient data in development.
- Treat blank allergy and medication fields as “not recorded,” never as “none.”
- Keep API validation and authorization on the server. Do not put secrets in `NEXT_PUBLIC_*` variables.
- Run the relevant test, lint, type-check, and production build commands before claiming completion.
- Update `PROJECT_LOG.md` and the related architecture documentation for each meaningful change.
