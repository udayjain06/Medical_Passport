import uuid

import pytest
from app.database import Base, enable_sqlite_foreign_keys
from app.models import EmergencyContact, PatientProfile, User
from sqlalchemy import create_engine, delete, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


def test_sqlite_enforces_valid_invalid_and_cascading_foreign_keys():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    user_id = uuid.uuid4()
    profile_id = uuid.uuid4()
    contact_id = uuid.uuid4()
    with Session(engine) as db:
        assert db.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
        db.add(
            EmergencyContact(
                id=uuid.uuid4(),
                profile_id=uuid.uuid4(),
                full_name="Invalid reference",
                phone_number="000",
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        db.add(User(id=user_id, email="fk@example.com", password_hash="hash"))
        db.add(
            PatientProfile(
                id=profile_id,
                user_id=user_id,
                full_name="Synthetic profile",
                is_primary=True,
            )
        )
        db.add(
            EmergencyContact(
                id=contact_id,
                profile_id=profile_id,
                full_name="Synthetic contact",
                phone_number="000",
            )
        )
        db.commit()
        assert db.get(PatientProfile, profile_id) is not None
        assert db.get(EmergencyContact, contact_id) is not None

        db.execute(delete(PatientProfile).where(PatientProfile.id == profile_id))
        db.commit()
        assert db.get(EmergencyContact, contact_id) is None
        assert db.get(User, user_id) is not None
    engine.dispose()
