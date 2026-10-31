import pytest

from app.api.common import APIError
from app.jobs import store
from app.storage.db import connect
from app.storage.migrations import migrate


def test_persist_and_replay_manual_intent(database):
    migrate()
    first = store.accept("+84900000001", "one", "manual", {})
    assert first["status"] == "queued"
    assert store.accept("+84900000001", "one", "manual", {})["run_id"] == first["run_id"]
    with pytest.raises(APIError) as exc:
        store.accept("+84900000001", "one", "mutation", {"method": "POST"})
    assert exc.value.status == 409
    with connect() as conn:
        assert conn.execute("SELECT count(*) n FROM sync.runs").fetchone()["n"] == 1


def test_mutation_intent_exists_before_source_call(database):
    migrate()
    run = store.accept("+84900000001", "one", "mutation", {"method": "POST"})
    assert run["status"] == "pending_mutation"
    with connect() as conn:
        assert conn.execute("SELECT request FROM sync.mutation_intents").fetchone()["request"] == {
            "method": "POST"
        }
