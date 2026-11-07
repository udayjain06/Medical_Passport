from fastapi import Request

from app.config import settings


def client_ip(request: Request) -> str:
    """Best-effort client IP. Only trusts X-Forwarded-For hops that our own proxies appended."""
    direct = request.client.host if request.client else "unknown"
    hops = settings.trusted_proxy_count
    if hops <= 0:
        return direct
    forwarded = [
        p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()
    ]
    if len(forwarded) >= hops:
        return forwarded[-hops]
    return direct
