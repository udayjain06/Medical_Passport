from __future__ import annotations

from pathlib import Path
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.config import settings
from app.crypto_storage import fernet

_MAGIC = b"MPENC1:"


def _fernet() -> MultiFernet | None:
    return fernet()


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
        raise RuntimeError("Encrypted document found but no DOCUMENT_ENCRYPTION_KEYS are set")
    try:
        return fernet.decrypt(raw[len(_MAGIC) :])
    except InvalidToken:
        raise RuntimeError("Document could not be decrypted with the configured key") from None


def reencrypt(profile_id: UUID, document_id: UUID) -> bool:
    """Re-encrypt a blob using the first configured key; plaintext legacy blobs are included."""
    encryption = _fernet()
    if encryption is None:
        raise RuntimeError("DOCUMENT_ENCRYPTION_KEYS must be set before rotating files")
    target = _safe_path(profile_id, document_id)
    raw = target.read_bytes()
    if raw.startswith(_MAGIC):
        encrypted = raw[len(_MAGIC) :]
        try:
            Fernet(settings.get_document_encryption_keys()[0].encode()).decrypt(encrypted)
            return False
        except InvalidToken:
            try:
                rotated = encryption.rotate(encrypted)
            except InvalidToken:
                raise RuntimeError(
                    "Document could not be decrypted with the configured keys"
                ) from None
            updated = _MAGIC + rotated
    else:
        updated = _MAGIC + encryption.encrypt(raw)

    temporary = target.with_suffix(".blob.tmp")
    temporary.write_bytes(updated)
    temporary.replace(target)
    return True


def delete(profile_id: UUID, document_id: UUID) -> None:
    target = _safe_path(profile_id, document_id)
    if target.exists():
        target.unlink()
        try:
            target.parent.rmdir()
        except OSError:
            pass
