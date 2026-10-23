"""Database connections.

Why a single factory: the rest of the pipeline (load.py) works against the
DBAPI interface (connect / cursor / commit) and never branches on backend.
Adding a third backend later means touching this file only.
"""
from __future__ import annotations

import sqlite3

from .config import Settings


def get_connection(settings: Settings):
    """Return a DBAPI connection for the configured backend."""
    if settings.backend == "sqlite":
        # Ensure the parent directory exists so the file DB can be created.
        settings.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(settings.sqlite_path))
        return conn
    if settings.backend == "postgres":
        import psycopg2  # imported lazily: not needed for sqlite runs

        return psycopg2.connect(
            host=settings.pg_host,
            port=settings.pg_port,
            dbname=settings.pg_db,
            user=settings.pg_user,
            password=settings.pg_password,
        )
    raise ValueError(f"Unknown backend: {settings.backend!r}")
