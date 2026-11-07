import pytest
from app.config import settings
from app.database import Base, enable_sqlite_foreign_keys, get_db
from app.main import app
from app.rate_limit import auth_rate_limiter
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture(autouse=True)
def reset_rate_limits():
    auth_rate_limiter._requests.clear()
    yield
    auth_rate_limiter._requests.clear()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "document_storage_path", tmp_path / "private_uploads")
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    testing_sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        db = testing_sessions()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, headers={"Origin": "http://localhost:3000"}) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()
