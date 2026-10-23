"""Load stage.

Job: create the warehouse table (if needed) and bulk-insert the validated frame.

Load semantics: FULL REFRESH. Each run deletes the table contents and
re-inserts. Why not incremental/upsert: the source file is a static,
versioned snapshot with no updated_at watermark — there is no reliable way
to detect "new or changed" rows, so pretending to do CDC would be dishonest.
Full refresh is simple, idempotent, and correct for this data shape.

Dialect handling: schema.sql carries {PK} and {NOW} placeholders, rendered
here per backend so the schema lives in exactly one file.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from .config import PROJECT_ROOT, Settings
from .db import get_connection

log = logging.getLogger(__name__)

SCHEMA_PATH = PROJECT_ROOT / "schema.sql"


def render_schema(backend: str) -> str:
    sql = SCHEMA_PATH.read_text()
    if backend == "sqlite":
        return sql.replace("{PK}", "INTEGER").replace("{NOW}", "CURRENT_TIMESTAMP")
    if backend == "postgres":
        return sql.replace("{PK}", "SERIAL").replace("{NOW}", "now()")
    raise ValueError(f"Unknown backend: {backend!r}")


def _to_native(value):
    """Convert pandas/numpy scalars to plain Python values for the driver.

    Why: DBAPI drivers choke on pd.NA / np.int64 / pd.Timestamp. Converting
    once here keeps the insert loop clean and backend-agnostic.
    datetime.date passes through untouched — both drivers bind it natively.
    """
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if hasattr(value, "item"):  # numpy scalar -> plain Python scalar
        return value.item()
    return value


def load(df: pd.DataFrame, settings: Settings) -> int:
    conn = get_connection(settings)
    try:
        cur = conn.cursor()
        log.info("Applying schema for backend=%s", settings.backend)
        # executescript-style: split on ';' and run each statement, because
        # neither sqlite3 nor psycopg2 cursor.execute runs multi-statement strings.
        for stmt in [s.strip() for s in render_schema(settings.backend).split(";") if s.strip()]:
            cur.execute(stmt)

        log.info("Clearing loans table (full-refresh semantics)")
        cur.execute("DELETE FROM loans")

        columns = [c for c in df.columns]
        placeholder = "%s" if settings.backend == "postgres" else "?"
        placeholders = ", ".join([placeholder] * len(columns))
        sql = f"INSERT INTO loans ({', '.join(columns)}) VALUES ({placeholders})"
        rows = [[_to_native(v) for v in row] for row in df[columns].itertuples(index=False)]
        cur.executemany(sql, rows)
        conn.commit()
        log.info("Loaded %d rows into loans", len(rows))
        return len(rows)
    finally:
        conn.close()
