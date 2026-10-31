"""One durable queue consumer, real-time intervals, and bounded recovery attempts."""

import logging
import threading
import time
from uuid import uuid4

from psycopg import OperationalError
from psycopg.errors import DeadlockDetected, SerializationFailure

from app.api.common import APIError
from app.jobs.store import accept, resolve_mutation
from app.pipeline.publish import publish
from app.storage.db import connect

log = logging.getLogger(__name__)


class Worker:
    def __init__(self, source, *, interval: int, clock=time.monotonic, wait=None) -> None:
        self.source, self.interval, self.clock = source, interval, clock
        self.stop_event, self.wake_event = threading.Event(), threading.Event()
        self.wait = wait or self.stop_event.wait
        self.next_due = clock()
        self.thread = threading.Thread(target=self.loop, name="sync-worker", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def close(self) -> None:
        self.stop_event.set()
        self.wake_event.set()
        self.thread.join(timeout=40)

    def wake(self) -> None:
        self.wake_event.set()

    def loop(self) -> None:
        while not self.stop_event.is_set():
            # Clear before inspecting the queue so a concurrent enqueue cannot be lost.
            self.wake_event.clear()
            try:
                if self.step():
                    continue
            except OperationalError:
                log.warning("sync stage=database code=DATABASE_UNAVAILABLE")
            except Exception:
                # Never log exception text: drivers/upstream payloads may contain sensitive data.
                log.error("sync stage=worker code=INTERNAL_ERROR")
            delay = max(0.1, min(1.0, self.next_due - self.clock())) if self.interval else 1
            self.wake_event.wait(delay)

    def step(self) -> bool:
        with connect() as lock:
            lock.autocommit = True
            if not lock.execute("SELECT pg_try_advisory_lock(8173605) locked").fetchone()["locked"]:
                return False
            with connect() as conn:
                run = conn.execute(
                    "SELECT * FROM sync.runs "
                    "WHERE status IN ('pending_mutation','queued','running') "
                    "ORDER BY created_at,run_id LIMIT 1"
                ).fetchone()
            if run is None and self.interval and self.clock() >= self.next_due:
                run = accept("interval", str(uuid4()), "interval", {})
            if run is None:
                return False
            self.process(run)
            self.next_due = self.clock() + self.interval
            return True

    def process(self, run: dict) -> None:
        run_id = run["run_id"]
        if run["status"] == "pending_mutation":
            while not self.stop_event.is_set():
                try:
                    response = resolve_mutation(run_id, self.source)
                except APIError:
                    return  # Rejection has already been persisted.
                if response["mutation_status"] != "pending":
                    break
                with connect() as conn:
                    attempts = conn.execute(
                        "SELECT attempts FROM sync.mutation_intents WHERE run_id=%s", (run_id,)
                    ).fetchone()["attempts"]
                self.wait(min(attempts, 2))
            with connect() as conn:
                run = conn.execute("SELECT * FROM sync.runs WHERE run_id=%s", (run_id,)).fetchone()
            if run["status"] != "queued":
                return
        while not self.stop_event.is_set():
            with connect() as conn:
                previous = conn.execute(
                    "SELECT status,attempts FROM sync.runs WHERE run_id=%s", (run_id,)
                ).fetchone()
                if previous["status"] in {"succeeded", "failed"}:
                    return
                if previous["attempts"] >= 3:
                    conn.execute(
                        "UPDATE sync.runs SET status='failed',finished_at=now(),"
                        "error_stage='synchronization',error_code='RETRY_EXHAUSTED' "
                        "WHERE run_id=%s",
                        (run_id,),
                    )
                    return
                run = conn.execute(
                    "UPDATE sync.runs SET status='running',started_at=COALESCE(started_at,now()),"
                    "attempts=attempts+1 WHERE run_id=%s RETURNING *",
                    (run_id,),
                ).fetchone()
            try:
                result = publish(self.source.snapshot(), run_id, run["minimum_revision"])
            except Exception as exc:
                code = exc.code if isinstance(exc, APIError) else "INTERNAL_ERROR"
                transient = isinstance(
                    exc, (OperationalError, DeadlockDetected, SerializationFailure)
                )
                if transient:
                    code = "DATABASE_UNAVAILABLE"
                transient = transient or (isinstance(exc, APIError) and exc.status >= 500)
                exhausted = run["attempts"] >= 3 or not transient
                with connect() as conn:
                    conn.execute(
                        "UPDATE sync.runs SET status=%s,error_stage='synchronization',"
                        "error_code=%s,finished_at=CASE WHEN %s THEN now() ELSE NULL END "
                        "WHERE run_id=%s AND status<>'succeeded'",
                        ("failed" if exhausted else "queued", code, exhausted, run_id),
                    )
                log.warning("sync run_id=%s stage=synchronization code=%s", run_id, code)
                if exhausted:
                    return
                self.wait(run["attempts"])
            else:
                log.info(
                    "sync run_id=%s stage=complete revision=%s",
                    run_id,
                    result["applied_source_revision"],
                )
                return
