from __future__ import annotations

import json
from typing import Any

from sqlalchemy.types import JSON, Text, TypeDecorator

from app.crypto_storage import decrypt_text, encrypt_text


class EncryptedText(TypeDecorator[str]):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, _dialect) -> str | None:
        return encrypt_text(value) if value is not None else None

    def process_result_value(self, value: str | None, _dialect) -> str | None:
        return decrypt_text(value) if value is not None else None


class EncryptedJSON(TypeDecorator[list[dict[str, Any]]]):
    impl = JSON
    cache_ok = True

    def process_bind_param(self, value: list[dict[str, Any]] | None, _dialect) -> str | None:
        if value is None:
            return None
        serialized = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        return encrypt_text(serialized)

    def process_result_value(self, value: Any, _dialect) -> list[dict[str, Any]]:
        if value is None:
            return []
        if isinstance(value, list):
            return value  # legacy plaintext JSON rows
        if not isinstance(value, str):
            raise RuntimeError("Stored extraction candidates are invalid")
        decoded = decrypt_text(value)
        try:
            result = json.loads(decoded)
        except json.JSONDecodeError:
            raise RuntimeError("Stored extraction candidates are invalid") from None
        if not isinstance(result, list):
            raise RuntimeError("Stored extraction candidates are invalid")
        return result
