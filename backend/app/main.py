from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import (
    abha,
    auth,
    documents,
    emergency,
    extraction,
    family,
    health,
    profile,
    timeline,
)

app = FastAPI(
    title="Medical Passport API",
    version="0.1.0",
    description=(
        "Private patient profile and authentication API. "
        "Medical history features are being built incrementally."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["Content-Type", "X-Requested-With"],
)


@app.middleware("http")
async def origin_and_cache_controls(request: Request, call_next):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if origin not in settings.cors_origins:
            return JSONResponse(status_code=403, content={"detail": "Untrusted request origin"})
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    if request.url.path.startswith("/api/public/emergency/"):
        response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return response


@app.exception_handler(RequestValidationError)
async def safe_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Do not echo submitted email, password, or health values in validation responses.
    errors = [
        {
            "loc": error.get("loc", []),
            "msg": error.get("msg", "Invalid value"),
            "type": error.get("type", "value_error"),
        }
        for error in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": errors})


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(documents.router)
app.include_router(extraction.router)
app.include_router(emergency.router)
app.include_router(timeline.router)
app.include_router(family.router)
app.include_router(abha.router)
