import os
import subprocess
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import MetaData, create_engine, select, text


def test_latest_migration_preserves_existing_records_and_backfills_provenance(tmp_path: Path):
    database_path = tmp_path / "migration-preserves-data.sqlite"
    database_url = f"sqlite:///{database_path.as_posix()}"
    backend_dir = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment.update(
        {
            "APP_ENV": "test",
            "DATABASE_URL": database_url,
            "DOCUMENT_STORAGE_PATH": str(tmp_path / "uploads"),
        }
    )
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "6fafbd8b528d"],
        cwd=backend_dir,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    user_id, profile_id, document_id, extraction_id, event_id = [uuid4().hex for _ in range(5)]
    timestamp = datetime.now(UTC)
    engine = create_engine(database_url)
    metadata = MetaData()
    metadata.reflect(bind=engine)
    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        connection.execute(
            metadata.tables["users"]
            .insert()
            .values(
                id=user_id,
                email="migration@example.com",
                password_hash="synthetic-hash",
                session_version=0,
                created_at=timestamp,
                updated_at=timestamp,
            )
        )
        connection.execute(
            metadata.tables["patient_profiles"]
            .insert()
            .values(
                id=profile_id,
                user_id=user_id,
                is_primary=True,
                full_name="Synthetic Migration Profile",
                created_at=timestamp,
                updated_at=timestamp,
            )
        )
        connection.execute(
            metadata.tables["medical_documents"]
            .insert()
            .values(
                id=document_id,
                profile_id=profile_id,
                uploaded_by_user_id=user_id,
                original_filename="synthetic-source.pdf",
                storage_key=f"{profile_id}/{document_id}.pdf",
                file_format="pdf",
                file_size=10,
                category="Laboratory Report",
                processing_status="confirmed",
                sha256_checksum="a" * 64,
                created_at=timestamp,
                updated_at=timestamp,
            )
        )
        connection.execute(
            metadata.tables["document_extractions"]
            .insert()
            .values(
                id=extraction_id,
                document_id=document_id,
                profile_id=profile_id,
                status="confirmed",
                ocr_text="Blood group O+",
                candidates=[{"field": "blood_group", "value": "O+", "source_page": 1}],
                engine_version="synthetic-test",
                created_at=timestamp,
                updated_at=timestamp,
            )
        )
        connection.execute(
            metadata.tables["timeline_events"]
            .insert()
            .values(
                id=event_id,
                profile_id=profile_id,
                source_document_id=document_id,
                title="Blood Group: O+",
                category="Medical observation",
                event_date=date(2025, 1, 2),
                summary="O+",
                source_page=1,
                provenance="patient_confirmed",
                verification_status="confirmed",
                created_at=timestamp,
                updated_at=timestamp,
            )
        )
    engine.dispose()

    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    engine = create_engine(database_url)
    metadata = MetaData()
    metadata.reflect(bind=engine)
    with engine.connect() as connection:
        profile = (
            connection.execute(
                select(metadata.tables["patient_profiles"]).where(
                    metadata.tables["patient_profiles"].c.id == profile_id
                )
            )
            .mappings()
            .one()
        )
        event = (
            connection.execute(
                select(metadata.tables["timeline_events"]).where(
                    metadata.tables["timeline_events"].c.id == event_id
                )
            )
            .mappings()
            .one()
        )
        assert profile["full_name"] == "Synthetic Migration Profile"
        assert profile["archived_at"] is None
        assert event["source_document_id"] == document_id
        assert event["source_extraction_id"] == extraction_id
        assert event["source_candidate_id"]
        assert event["source_document_filename"] == "synthetic-source.pdf"
        assert event["source_document_checksum"] == "a" * 64
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
    engine.dispose()
