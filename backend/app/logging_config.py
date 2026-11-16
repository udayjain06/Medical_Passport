from __future__ import annotations

import json
import logging
import re
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

request_id_context: ContextVar[str] = ContextVar("medical_passport_request_id", default="-")

_SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)\b(password|token|authorization|cookie|secret|api[_-]?key)\b"
    r"(\s*[:=]\s*)(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)"
)
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*")
_EMERGENCY_TOKEN_PATH = re.compile(r"(?i)(/api/public/emergency/|/emergency/)([^/\s?\"']+)")
_IPV4 = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?::\d{1,5})?(?![\w.])")
_IPV6 = re.compile(r"(?<![A-Za-z0-9])(?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4}(?![A-Za-z0-9])")


def redact_message(message: str) -> str:
    safe = _SENSITIVE_ASSIGNMENT.sub(r"\1\2<redacted>", message)
    safe = _BEARER.sub("Bearer <redacted>", safe)
    safe = _EMERGENCY_TOKEN_PATH.sub(r"\1<redacted>", safe)
    safe = _IPV6.sub("<ip>", safe)
    return _IPV4.sub("<ip>", safe)


def safe_request_path(path: str) -> str:
    if path.startswith("/api/public/emergency/"):
        return "/api/public/emergency/{token}"
    if path.startswith("/emergency/"):
        return "/emergency/{token}"
    return path


class RedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = redact_message(record.getMessage())
            record.args = ()
        except Exception:
            record.msg = "<redacted log message>"
            record.args = ()
        if not hasattr(record, "request_id"):
            record.request_id = request_id_context.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_message(record.getMessage()),
            "request_id": getattr(record, "request_id", request_id_context.get()),
        }
        for field in ("method", "path", "status_code", "duration_ms"):
            if hasattr(record, field):
                value = getattr(record, field)
                data[field] = redact_message(str(value)) if isinstance(value, str) else value
        return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def configure_logging() -> None:
    root = logging.getLogger()
    if not root.handlers:
        root.addHandler(logging.StreamHandler())
    for name in ("", "uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        if not any(isinstance(item, RedactionFilter) for item in logger.filters):
            logger.addFilter(RedactionFilter())
        for handler in logger.handlers:
            handler.setFormatter(JsonFormatter())
            if not any(isinstance(item, RedactionFilter) for item in handler.filters):
                handler.addFilter(RedactionFilter())
