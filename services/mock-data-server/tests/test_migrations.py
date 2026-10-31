import pytest
from psycopg.errors import CheckViolation

from app.storage.db import connect
from app.storage.migrations import migrate


def test_migration_replay_preserves_unrelated_data(database):
    with connect() as conn:
        conn.execute("CREATE TABLE public.sentinel (value integer)")
        conn.execute("INSERT INTO public.sentinel VALUES (42)")
    migrate()
    migrate()
    with connect() as conn:
        assert conn.execute("SELECT value FROM public.sentinel").fetchone()["value"] == 42
        assert conn.execute("SELECT count(*) AS n FROM mock.schema_migrations").fetchone()["n"] >= 1


def test_phone_identity_constraints(database):
    migrate()
    with pytest.raises(CheckViolation), connect() as conn:
        conn.execute(
            "INSERT INTO mock.users (user_id, display_name, is_active) VALUES (%s, %s, true)",
            ("not-a-phone", "Demo"),
        )
