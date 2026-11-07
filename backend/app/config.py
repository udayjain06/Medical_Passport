from __future__ import annotations

import secrets
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(48))
    database_url: str = "sqlite:///./medical_passport.db"
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]
    session_ttl_minutes: int = Field(default=720, ge=5, le=10080)
    cookie_secure: bool = False
    auth_rate_limit_count: int = Field(default=10, ge=1, le=1000)
    auth_rate_limit_window_seconds: int = Field(default=600, ge=1, le=86400)
    document_storage_path: Path = BACKEND_DIR / "private_uploads"
    document_max_size_bytes: int = Field(default=10 * 1024 * 1024, ge=1024, le=100 * 1024 * 1024)
    public_app_url: str = "http://localhost:3000"
    # Number of trusted reverse proxies in front of the API (Next.js proxy = 1). 0 = use socket IP.
    trusted_proxy_count: int = Field(default=0, ge=0, le=5)
    # Fernet key (urlsafe base64, 32 bytes). Required in production; encrypts stored documents.
    document_encryption_key: str | None = None
    emergency_max_hours: int = Field(default=8760, ge=1, le=87600)
    emergency_access_rate_per_minute: int = Field(default=30, ge=1, le=1000)
    medical_ai_endpoint: str | None = None
    medical_ai_api_key: str | None = None
    medical_ai_model: str | None = None

    @model_validator(mode="after")
    def validate_production_security(self) -> Settings:
        placeholder = "GENERATE_A_UNIQUE_SECRET_WITH_THE_COMMAND_ABOVE"
        if self.app_env == "production":
            if len(self.secret_key) < 32 or self.secret_key == placeholder:
                raise ValueError("SECRET_KEY must be a unique value of at least 32 characters")
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE must be true in production")
            if not self.document_encryption_key:
                raise ValueError("DOCUMENT_ENCRYPTION_KEY is required in production")
            try:
                from cryptography.fernet import Fernet

                Fernet(self.document_encryption_key.encode())
            except Exception:
                raise ValueError("DOCUMENT_ENCRYPTION_KEY must be a valid Fernet key") from None
            if any(not o.startswith("https://") for o in self.cors_origins):
                raise ValueError("CORS_ORIGINS must be explicit https origins in production")
            if not self.public_app_url.startswith("https://"):
                raise ValueError("PUBLIC_APP_URL must use https in production")
            if not self.database_url.startswith("postgresql+psycopg://"):
                raise ValueError("Production DATABASE_URL must use the PostgreSQL psycopg driver")
        elif self.secret_key == placeholder:
            # The example value is deliberately unusable as a real signing key.
            self.secret_key = secrets.token_urlsafe(48)
        return self


settings = Settings()
