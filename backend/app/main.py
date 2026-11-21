import logging
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.logging_config import configure_logging, request_id_context, safe_request_path
from app.request_limits import RequestSizeLimitMiddleware
from app.routers import (
    abha,
    auth,
    documents,
    emergency,
    export,
    extraction,
    family,
    health,
    profile,
    timeline,
)

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Medical Passport API",
    version="0.1.0",
    docs_url=None if settings.app_env == "production" else "/docs",
    redoc_url=None if settings.app_env == "production" else "/redoc",
    openapi_url=None if settings.app_env == "production" else "/openapi.json",
    description=(
        "Private patient profile and authentication API. "
        "Medical history features are being built incrementally."
    ),
)

app.add_middleware(RequestSizeLimitMiddleware, max_bytes=settings.request_max_size_bytes)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["Content-Type", "X-Requested-With"],
)


@app.middleware("http")
async def origin_and_cache_controls(request: Request, call_next):
    request_id = uuid4().hex
    context_token = request_id_context.set(request_id)
    started = perf_counter()
    try:
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if origin not in settings.cors_origins:
                response = JSONResponse(
                    status_code=403,
                    content={"detail": "Untrusted request origin"},
                )
            else:
                response = await call_next(request)
        else:
            response = await call_next(request)
        response.headers["Cache-Control"] = "no-store, private"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = (
            "no-referrer"
            if request.url.path.startswith(("/emergency/", "/api/public/emergency/"))
            else "strict-origin-when-cross-origin"
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data:; "
            "connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
        )
        response.headers["Permissions-Policy"] = "camera=(self), microphone=(), geolocation=()"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Request-ID"] = request_id
        if request.url.path.startswith("/api/public/emergency/"):
            response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        logger.info(
            "http_request",
            extra={
                "method": request.method,
                "path": safe_request_path(request.url.path),
                "status_code": response.status_code,
                "duration_ms": round((perf_counter() - started) * 1000, 2),
                "request_id": request_id,
            },
        )
        return response
    finally:
        request_id_context.reset(context_token)


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
app.include_router(export.router)
app.include_router(timeline.router)
app.include_router(family.router)
app.include_router(abha.router)
app.add_api_route("/healthz", health.live, methods=["GET"], include_in_schema=False)
app.add_api_route("/readyz", health.ready, methods=["GET"], include_in_schema=False)
