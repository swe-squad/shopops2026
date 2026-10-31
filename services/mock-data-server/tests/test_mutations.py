from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from app.api.common import APIError
from app.storage.db import connect
from app.storage.migrations import migrate
from app.storage.mutations import mutate


def create_user(conn, revision):
    conn.execute(
        "INSERT INTO mock.users (user_id,display_name) VALUES (%s,%s)",
        ("+84900000001", "Demo"),
    )
    return {"user_id": "+84900000001"}


def test_receipt_replays_and_changed_intent_conflicts(database):
    migrate()
    first = mutate("admin", "one", {"name": "Demo"}, create_user)
    assert mutate("admin", "one", {"name": "Demo"}, create_user) == first
    with pytest.raises(APIError) as exc:
        mutate("admin", "one", {"name": "Other"}, create_user)
    assert exc.value.status == 409
    with connect() as conn:
        assert conn.execute("SELECT revision FROM mock.state").fetchone()["revision"] == 1
        assert conn.execute("SELECT count(*) AS n FROM mock.users").fetchone()["n"] == 1


def test_failed_write_leaves_no_receipt_or_revision(database):
    migrate()

    def fail(conn, revision):
        create_user(conn, revision)
        raise ValueError("controlled failure")

    with pytest.raises(ValueError):
        mutate("admin", "one", {}, fail)
    with connect() as conn:
        assert conn.execute("SELECT revision FROM mock.state").fetchone()["revision"] == 0
        assert conn.execute("SELECT count(*) AS n FROM mock.users").fetchone()["n"] == 0
    assert mutate("admin", "one", {}, create_user)["source_revision"] == 1


def test_inflight_duplicate_has_one_effect(database):
    migrate()
    entered, release = Event(), Event()

    def slow(conn, revision):
        entered.set()
        assert release.wait(5)
        return create_user(conn, revision)

    with ThreadPoolExecutor() as pool:
        future = pool.submit(mutate, "admin", "one", {}, slow)
        assert entered.wait(5)
        try:
            with pytest.raises(APIError) as exc:
                mutate("admin", "one", {}, create_user)
            assert exc.value.code == "MUTATION_IN_PROGRESS"
        finally:
            release.set()
        first = future.result()
    assert mutate("admin", "one", {}, create_user) == first
