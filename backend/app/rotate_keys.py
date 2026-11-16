from __future__ import annotations

import sys

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app import document_storage
from app.config import settings
from app.database import SessionLocal
from app.models import DocumentExtraction, MedicalDocument


def rotate_data(db: Session) -> tuple[int, int]:
    """Re-encrypt private document blobs and extraction fields with the primary key."""
    if not settings.get_document_encryption_keys():
        raise RuntimeError("DOCUMENT_ENCRYPTION_KEYS must be configured before rotation")

    documents = db.scalars(select(MedicalDocument)).all()
    for document in documents:
        document_storage.reencrypt(document.profile_id, document.id)

    extractions = db.scalars(select(DocumentExtraction)).all()
    for extraction in extractions:
        if extraction.ocr_text is not None:
            flag_modified(extraction, "ocr_text")
        flag_modified(extraction, "candidates")

    db.commit()
    return len(documents), len(extractions)


def main() -> int:
    db = SessionLocal()
    try:
        blobs, extractions = rotate_data(db)
    except Exception:
        db.rollback()
        print(
            "Key rotation failed. Keep all old and new keys configured, "
            "restore from backup if needed, and investigate before retrying.",
            file=sys.stderr,
        )
        return 1
    finally:
        db.close()

    print(f"Re-encrypted {blobs} document blobs and {extractions} extraction records.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
