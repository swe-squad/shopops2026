import pytest

from app.api.common import APIError
from app.jobs.store import accept, resolve_mutation
from app.jobs.worker import Worker
from app.storage.db import connect
from app.storage.migrations import migrate
from tests.test_normalization import full_snapshot


class Source:
    calls = 0

    def snapshot(self):
        self.calls += 1
        return full_snapshot()


def test_manual_queue_and_committed_restart(database):
    migrate()
    run = accept("+84900000001", "manual", "manual", {})
    source = Source()
    worker = Worker(source, interval=0, wait=lambda _: None)
    assert worker.step()
    assert not worker.step()
    with connect() as conn:
        row = conn.execute("SELECT * FROM sync.runs WHERE run_id=%s", (run["run_id"],)).fetchone()
        assert row["status"] == "succeeded" and row["applied_revision"] == 1
    assert not Worker(source, interval=0).step()
    assert source.calls == 1


@pytest.mark.parametrize("status,expected", [(503, 3), (422, 1)])
def test_bounded_retry(database, status, expected):
    migrate()
    accept("+84900000001", "manual", "manual", {})

    class Broken(Source):
        def snapshot(self):
            self.calls += 1
            raise APIError(status, "SOURCE_UNAVAILABLE" if status == 503 else "INVALID_SNAPSHOT")

    source = Broken()
    Worker(source, interval=0, wait=lambda _: None).step()
    with connect() as conn:
        row = conn.execute("SELECT * FROM sync.runs").fetchone()
        assert row["status"] == "failed" and row["attempts"] == expected
    assert source.calls == expected


def test_unknown_source_outcome_can_resume_same_intent(database):
    migrate()
    request = {"method": "POST", "path": "/v1/entities/products", "body": {}}
    run = accept("+84900000001", "write", "mutation", request)

    class Ambiguous(Source):
        unavailable = True
        keys = []

        def request(self, method, path, **kwargs):
            self.keys.append(kwargs["key"])
            if self.unavailable:
                raise APIError(503, "SOURCE_UNAVAILABLE")
            return {"data": {"sku": "one"}, "source_revision": 1}

    source = Ambiguous()
    assert resolve_mutation(run["run_id"], source)["mutation_status"] == "pending"
    Worker(source, interval=0, wait=lambda _: None).step()
    with connect() as conn:
        row = conn.execute("SELECT * FROM sync.runs").fetchone()
        assert row["error_code"] == "SOURCE_OUTCOME_UNKNOWN"
    source.unavailable = False
    resumed = accept("+84900000001", "write", "mutation", request)
    assert resumed["run_id"] == run["run_id"]
    Worker(source, interval=0, wait=lambda _: None).step()
    assert source.keys == ["write"] * 4
    with connect() as conn:
        assert conn.execute("SELECT status FROM sync.runs").fetchone()["status"] == "succeeded"


def test_interval_waits_after_queue_drain(database):
    migrate()
    now = [0]
    worker = Worker(Source(), interval=10, clock=lambda: now[0], wait=lambda _: None)
    assert worker.step()
    assert not worker.step()
    now[0] = 9
    assert not worker.step()
    now[0] = 10
    assert worker.step()
    with connect() as conn:
        assert conn.execute("SELECT count(*) n FROM sync.runs").fetchone()["n"] == 2
        assert str(conn.execute("SELECT as_of FROM mart.settings").fetchone()["as_of"]).startswith(
            "2026-10-30 17:00"
        )


def test_source_inflight_conflict_remains_pending(database):
    migrate()
    run = accept(
        "+84900000001",
        "inflight",
        "mutation",
        {"method": "POST", "path": "/v1/entities/products", "body": {}},
    )

    class Busy:
        def request(self, *args, **kwargs):
            raise APIError(409, "MUTATION_IN_PROGRESS")

    result = resolve_mutation(run["run_id"], Busy())
    assert result["mutation_status"] == "pending"
    assert result["sync_status"] == "pending_mutation"


def test_second_worker_cannot_consume_while_global_lock_is_held(database):
    migrate()
    accept("+84900000001", "locked", "manual", {})
    source = Source()
    worker = Worker(source, interval=0, wait=lambda _: None)
    with connect() as owner:
        owner.execute("SELECT pg_advisory_lock(8173605)")
        assert not worker.step()
        assert source.calls == 0
        with connect() as conn:
            assert conn.execute("SELECT status FROM sync.runs").fetchone()["status"] == "queued"
    assert worker.step()
    assert source.calls == 1
