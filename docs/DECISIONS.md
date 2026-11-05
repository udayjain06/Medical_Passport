# Architecture Decisions

## 2026-11-04 — Preserve the preferred stack in an empty repository

The target directory was empty, so initialize the specified Next.js/React/TypeScript and FastAPI/Pydantic/SQLAlchemy/Alembic stack rather than selecting a substitute.

## 2026-11-04 — SQLite for local development, PostgreSQL for deployment

Docker was unavailable in the implementation environment. SQLite keeps local setup and tests runnable without pretending it is the production database. The production URL is configurable for PostgreSQL through psycopg.

## 2026-11-04 — Same-origin HttpOnly session cookie

The browser calls a Next.js `/api` rewrite and does not store tokens in local storage. FastAPI signs a short-lived cookie, validates user/session version on every protected request, and enforces an allowed Origin for writes. Logout increments the user session version.

## 2026-11-04 — Keep phase boundaries visible

Landing-page status labels match implemented workflows: the vault card describes local OCR and human source review, while the emergency card describes consent-controlled QR links. ABHA linking remains explicitly marked externally blocked; no unavailable workflow is presented as successful.

## 2026-11-05 — Limit Next.js build workers on Windows

Parallel static prerendering intermittently failed with `EPERM` while creating route-segment directories on the target Windows filesystem. Set Next.js `experimental.cpus` to `1`; the production build then completed. Reassess this local build setting on the deployment platform.
