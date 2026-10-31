from app.storage.db import connect
from app.storage.migrations import migrate


def test_migration_replay_and_owned_schemas(database):
    with connect() as conn:
        conn.execute("CREATE TABLE public.sentinel (value integer)")
        conn.execute("INSERT INTO public.sentinel VALUES (42)")
    migrate()
    migrate()
    with connect() as conn:
        assert conn.execute("SELECT value FROM public.sentinel").fetchone()["value"] == 42
        assert (
            conn.execute("SELECT to_regclass('core.orders') AS name").fetchone()["name"]
            == "core.orders"
        )
        assert conn.execute("SELECT revision FROM sync.state").fetchone()["revision"] == -1
        assert conn.execute("SELECT to_regclass('mock.users') AS name").fetchone()["name"] is None
