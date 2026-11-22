"""Command-line entry point for the development-only synthetic demo seed."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.demo_seed import main  # noqa: E402


if __name__ == "__main__":
    main()
