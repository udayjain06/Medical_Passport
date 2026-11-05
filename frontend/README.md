# Medical Passport frontend

The project setup and end-to-end run instructions are in the repository [README](../README.md).

This Next.js App Router app proxies browser requests under `/api/*` to the FastAPI backend. Set `API_ORIGIN` in `.env.local` only when the backend is not at `http://127.0.0.1:8000`. The production build and browser journey should be run alongside the backend as described in the root README.
