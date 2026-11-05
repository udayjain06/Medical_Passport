from __future__ import annotations

from pathlib import Path
from uuid import UUID

from app.config import settings


def _safe_path(profile_id: UUID, document_id: UUID) -> Path:
    root = settings.document_storage_path.resolve()
    target = (root / str(profile_id) / f"{document_id}.blob").resolve()
    if not target.is_relative_to(root):
        raise ValueError("Invalid storage path")
    return target


def save(profile_id: UUID, document_id: UUID, data: bytes) -> str:
    target = _safe_path(profile_id, document_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return f"{profile_id}/{document_id}.blob"


def read(profile_id: UUID, document_id: UUID) -> bytes:
    return _safe_path(profile_id, document_id).read_bytes()


def delete(profile_id: UUID, document_id: UUID) -> None:
    target = _safe_path(profile_id, document_id)
    if target.exists():
        target.unlink()
        try:
            target.parent.rmdir()
        except OSError:
            pass
