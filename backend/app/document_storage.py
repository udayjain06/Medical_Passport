from __future__ import annotations

from pathlib import Path
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

_MAGIC = b"MPENC1:"


def _fernet() -> Fernet | None:
    return (
        Fernet(settings.document_encryption_key.encode())
        if settings.document_encryption_key
        else None
    )


def _safe_path(profile_id: UUID, document_id: UUID) -> Path:
    root = settings.document_storage_path.resolve()
    target = (root / str(profile_id) / f"{document_id}.blob").resolve()
    if not target.is_relative_to(root):
        raise ValueError("Invalid storage path")
    return target


def save(profile_id: UUID, document_id: UUID, data: bytes) -> str:
    target = _safe_path(profile_id, document_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    fernet = _fernet()
    target.write_bytes(_MAGIC + fernet.encrypt(data) if fernet else data)
    return f"{profile_id}/{document_id}.blob"


def read(profile_id: UUID, document_id: UUID) -> bytes:
    raw = _safe_path(profile_id, document_id).read_bytes()
    if not raw.startswith(_MAGIC):
        return raw  # legacy plaintext blob written before encryption was enabled
    fernet = _fernet()
    if fernet is None:
        raise RuntimeError("Encrypted document found but DOCUMENT_ENCRYPTION_KEY is not set")
    try:
        return fernet.decrypt(raw[len(_MAGIC) :])
    except InvalidToken:
        raise RuntimeError("Document could not be decrypted with the configured key") from None


def delete(profile_id: UUID, document_id: UUID) -> None:
    target = _safe_path(profile_id, document_id)
    if target.exists():
        target.unlink()
        try:
            target.parent.rmdir()
        except OSError:
            pass
