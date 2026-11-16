from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AuthActionToken, User

AuthPurpose = Literal["email_verification", "password_reset"]


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def revoke_tokens(db: Session, user_id: UUID, purpose: AuthPurpose) -> None:
    db.execute(
        update(AuthActionToken)
        .where(
            AuthActionToken.user_id == user_id,
            AuthActionToken.purpose == purpose,
            AuthActionToken.used_at.is_(None),
        )
        .values(used_at=datetime.now(UTC))
    )


def issue_token(
    db: Session,
    user_id: UUID,
    purpose: AuthPurpose,
    lifetime: timedelta,
) -> str:
    now = datetime.now(UTC)
    expires_at = now + lifetime
    payload = {
        "sub": str(user_id),
        "purpose": purpose,
        "exp": int(expires_at.timestamp()),
        "nonce": secrets.token_urlsafe(24),
    }
    payload_part = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(
        settings.secret_key.encode("utf-8"), payload_part.encode("ascii"), hashlib.sha256
    ).digest()
    token = f"{payload_part}.{_b64encode(signature)}"
    db.add(
        AuthActionToken(
            user_id=user_id,
            purpose=purpose,
            token_hash=token_hash(token),
            expires_at=expires_at,
        )
    )
    return token


def consume_token(db: Session, token: str, purpose: AuthPurpose) -> User | None:
    if len(token) > 2048:
        return None
    try:
        payload_part, signature_part = token.split(".", maxsplit=1)
        signature = _b64decode(signature_part)
        expected = hmac.new(
            settings.secret_key.encode("utf-8"), payload_part.encode("ascii"), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(signature, expected):
            return None
        payload = json.loads(_b64decode(payload_part))
        user_id = UUID(payload["sub"])
        expiry = int(payload["exp"])
    except (ValueError, TypeError, KeyError, UnicodeError, json.JSONDecodeError, binascii.Error):
        return None

    if not isinstance(payload, dict):
        return None

    now = datetime.now(UTC)
    if payload.get("purpose") != purpose or expiry <= int(now.timestamp()):
        return None

    stored = db.scalar(
        select(AuthActionToken).where(
            AuthActionToken.token_hash == token_hash(token),
            AuthActionToken.purpose == purpose,
            AuthActionToken.user_id == user_id,
        )
    )
    if stored is None or stored.used_at is not None:
        return None
    expires_at = stored.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= now:
        return None

    user = db.get(User, user_id)
    if user is None:
        return None
    stored.used_at = now
    return user
