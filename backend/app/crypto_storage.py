from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.config import settings

ENCRYPTED_PREFIX = "MPENC1:"


def fernet() -> MultiFernet | None:
    keys = settings.get_document_encryption_keys()
    if not keys:
        return None
    return MultiFernet([Fernet(key.encode("ascii")) for key in keys])


def encrypt_text(value: str) -> str:
    encryption = fernet()
    if encryption is None:
        return value
    token = encryption.encrypt(value.encode("utf-8")).decode("ascii")
    return ENCRYPTED_PREFIX + token


def decrypt_text(value: str) -> str:
    if not value.startswith(ENCRYPTED_PREFIX):
        return value
    encryption = fernet()
    if encryption is None:
        raise RuntimeError("Encrypted health data found but no DOCUMENT_ENCRYPTION_KEYS are set")
    token = value[len(ENCRYPTED_PREFIX) :].encode("ascii")
    try:
        return encryption.decrypt(token).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError):
        raise RuntimeError("Health data could not be decrypted with the configured keys") from None


def encryption_is_active() -> bool:
    return fernet() is not None
