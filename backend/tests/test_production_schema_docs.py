import importlib

from app.config import settings
from fastapi.testclient import TestClient


def test_schema_routes_are_disabled_in_production(monkeypatch):
    import app.main as main_module

    monkeypatch.setattr(settings, "app_env", "production")
    production_main = importlib.reload(main_module)
    try:
        with TestClient(production_main.app) as client:
            for path in ("/docs", "/redoc", "/openapi.json"):
                assert client.get(path).status_code == 404
    finally:
        monkeypatch.setattr(settings, "app_env", "test")
        importlib.reload(main_module)
