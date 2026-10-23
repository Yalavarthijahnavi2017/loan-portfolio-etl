"""Project configuration.

Why a dataclass instead of loose os.getenv calls scattered everywhere:
every setting has one definition, one type, and one default. The pipeline
fails fast at startup if the environment is misconfigured, instead of
halfway through a load.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load .env if present; environment variables always win over the file.
load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    backend: str          # "sqlite" or "postgres"
    sqlite_path: Path
    pg_host: str
    pg_port: int
    pg_db: str
    pg_user: str
    pg_password: str
    raw_csv_path: Path
    source_url: str
    refresh_source: bool


SOURCE_URL = (
    "https://www.openintro.org/data/csv/loans_full_schema.csv"
)


def load_settings() -> Settings:
    backend = os.getenv("DB_BACKEND", "sqlite").strip().lower()
    if backend not in ("sqlite", "postgres"):
        raise ValueError(
            f"DB_BACKEND must be 'sqlite' or 'postgres', got {backend!r}"
        )
    return Settings(
        backend=backend,
        sqlite_path=PROJECT_ROOT / os.getenv("SQLITE_PATH", "data/warehouse/loans.db"),
        pg_host=os.getenv("POSTGRES_HOST", "localhost"),
        pg_port=int(os.getenv("POSTGRES_PORT", "5432")),
        pg_db=os.getenv("POSTGRES_DB", "loans_dw"),
        pg_user=os.getenv("POSTGRES_USER", "etl_user"),
        pg_password=os.getenv("POSTGRES_PASSWORD", ""),
        raw_csv_path=PROJECT_ROOT / "data" / "raw" / "loans.csv",
        source_url=SOURCE_URL,
        refresh_source=os.getenv("REFRESH_SOURCE", "0") == "1",
    )
