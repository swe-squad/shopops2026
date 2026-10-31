"""Transactional, checksummed migrations for source-owned tables."""

import hashlib
from pathlib import Path

from app.storage.db import connect

DIRECTORY = Path(__file__).resolve().parents[1] / "migrations"


def migrate() -> None:
    with connect() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(8173601)")
        conn.execute("CREATE SCHEMA IF NOT EXISTS mock")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS mock.schema_migrations "
            "(name text PRIMARY KEY, checksum text NOT NULL)"
        )
        for path in sorted(DIRECTORY.glob("*.sql")):
            content = path.read_text(encoding="utf-8")
            checksum = hashlib.sha256(content.encode()).hexdigest()
            row = conn.execute(
                "SELECT checksum FROM mock.schema_migrations WHERE name=%s", (path.name,)
            ).fetchone()
            if row:
                if row["checksum"] != checksum:
                    raise RuntimeError(f"Applied migration changed: {path.name}")
                continue
            conn.execute(content)
            conn.execute("INSERT INTO mock.schema_migrations VALUES (%s,%s)", (path.name, checksum))
