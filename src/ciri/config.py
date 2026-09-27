"""Runtime paths and environment settings.

The warehouse defaults to a local SQLite file so the platform runs without
a database server. Set DATABASE_URL to a PostgreSQL URL when the star
schema should live in Postgres (see docker-compose.yml).
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = Path(__file__).resolve().parent

DATA_DIR = Path(os.environ.get("CIRI_DATA_DIR", PROJECT_ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
QUARANTINE_DIR = DATA_DIR / "quarantine"
WAREHOUSE_DIR = DATA_DIR / "warehouse"
MODEL_DIR = Path(os.environ.get("CIRI_MODEL_DIR", PROJECT_ROOT / "models"))
SQL_DIR = PROJECT_ROOT / "sql"
LOG_DIR = Path(os.environ.get("CIRI_LOG_DIR", PROJECT_ROOT / "logs"))
POWERBI_DIR = PROJECT_ROOT / "dashboards" / "powerbi" / "extracts"

DEFAULT_SQLITE = WAREHOUSE_DIR / "ciri.db"


def database_url() -> str:
    """Return the SQLAlchemy URL for the warehouse."""
    configured = os.environ.get("DATABASE_URL", "").strip()
    if configured:
        return configured
    return f"sqlite:///{DEFAULT_SQLITE}"


def openai_settings() -> dict[str, str]:
    """OpenAI-compatible chat settings. The key may be empty."""
    return {
        "api_key": os.environ.get("OPENAI_API_KEY", "").strip(),
        "base_url": os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
        "model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
    }


PRODUCTION_START = date(2024, 1, 1)
PRODUCTION_END = date(2025, 6, 30)
