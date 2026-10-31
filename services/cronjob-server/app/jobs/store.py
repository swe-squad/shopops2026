"""Durable run and source intent transitions, with stable caller idempotency."""

from uuid import uuid4

from psycopg.types.json import Jsonb

from app.api.common import APIError
from app.pipeline.publish import digest
from app.storage.db import connect


def accept(actor: str, key: str, trigger: str, intent: dict) -> dict:
    if not key or len(key) > 200:
        raise APIError(422, "INVALID_IDEMPOTENCY_KEY")
    fingerprint = digest({"trigger": trigger, "intent": intent})
    with connect() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,8173604))", (actor + key,))
        previous = conn.execute(
            "SELECT * FROM sync.runs WHERE actor=%s AND idempotency_key=%s FOR UPDATE",
            (actor, key),
        ).fetchone()
        if previous:
            if previous["intent_hash"] != fingerprint:
                raise APIError(409, "IDEMPOTENCY_CONFLICT")
            if previous["error_code"] == "SOURCE_OUTCOME_UNKNOWN":
                conn.execute(
                    "UPDATE sync.runs SET status='pending_mutation',attempts=0,"
                    "error_code=NULL,error_stage=NULL,finished_at=NULL WHERE run_id=%s",
                    (previous["run_id"],),
                )
                conn.execute(
                    "UPDATE sync.mutation_intents SET status='pending',attempts=0 WHERE run_id=%s",
                    (previous["run_id"],),
                )
                previous["status"] = "pending_mutation"
            return previous
        run_id = uuid4()
        row = conn.execute(
            "INSERT INTO sync.runs(run_id,actor,idempotency_key,intent_hash,trigger,status) "
            "VALUES (%s,%s,%s,%s,%s,%s) RETURNING *",
            (
                run_id,
                actor,
                key,
                fingerprint,
                trigger,
                "pending_mutation" if trigger == "mutation" else "queued",
            ),
        ).fetchone()
        if trigger == "mutation":
            conn.execute(
                "INSERT INTO sync.mutation_intents(run_id,request) VALUES (%s,%s)",
                (run_id, Jsonb(intent)),
            )
        return row


def resolve_mutation(run_id, source) -> dict:
    """Row lock serializes HTTP attempts; intent was committed before entering here."""
    rejection = None
    with connect() as conn:
        run = conn.execute(
            "SELECT * FROM sync.runs WHERE run_id=%s FOR UPDATE", (run_id,)
        ).fetchone()
        intent = conn.execute(
            "SELECT * FROM sync.mutation_intents WHERE run_id=%s FOR UPDATE", (run_id,)
        ).fetchone()
        if intent["status"] == "rejected":
            raise APIError(intent["rejection_status"], run["error_code"])
        if intent["status"] == "applied":
            return mutation_response(run, intent)
        request = intent["request"]
        try:
            response = source.request(
                request["method"],
                request["path"],
                actor=run["actor"],
                key=run["idempotency_key"],
                params=request.get("params"),
                body=request.get("body"),
            )
            if (
                not isinstance(response.get("source_revision"), int)
                or response["source_revision"] < 0
                or "data" not in response
            ):
                raise APIError(503, "INVALID_SOURCE_RESPONSE")
        except APIError as exc:
            # Invalid/ambiguous upstream replies cannot prove that the write failed.
            transient = exc.status >= 500 or exc.code in {
                "INVALID_SOURCE_RESPONSE",
                "IDEMPOTENCY_IN_PROGRESS",
            }
            attempts = intent["attempts"] + 1
            if transient:
                exhausted = attempts >= 3
                conn.execute(
                    "UPDATE sync.mutation_intents SET attempts=%s,status=%s WHERE run_id=%s",
                    (attempts, "unknown" if exhausted else "pending", run_id),
                )
                conn.execute(
                    "UPDATE sync.runs SET status=%s,error_code=%s,error_stage='mutation',"
                    "finished_at=CASE WHEN %s THEN now() ELSE NULL END WHERE run_id=%s",
                    (
                        "failed" if exhausted else "pending_mutation",
                        "SOURCE_OUTCOME_UNKNOWN" if exhausted else exc.code,
                        exhausted,
                        run_id,
                    ),
                )
            else:
                conn.execute(
                    "UPDATE sync.mutation_intents SET status='rejected',"
                    "rejection_status=%s,attempts=%s WHERE run_id=%s",
                    (exc.status, attempts, run_id),
                )
                conn.execute(
                    "UPDATE sync.runs SET status='failed',error_stage='mutation',"
                    "error_code=%s,finished_at=now() WHERE run_id=%s",
                    (exc.code, run_id),
                )
                rejection = exc
        else:
            conn.execute(
                "UPDATE sync.mutation_intents SET status='applied',response=%s,"
                "attempts=attempts+1 WHERE run_id=%s",
                (Jsonb(response), run_id),
            )
            conn.execute(
                "UPDATE sync.runs SET status='queued',minimum_revision=%s,"
                "error_code=NULL,error_stage=NULL WHERE run_id=%s",
                (response["source_revision"], run_id),
            )
        run = conn.execute("SELECT * FROM sync.runs WHERE run_id=%s", (run_id,)).fetchone()
        intent = conn.execute(
            "SELECT * FROM sync.mutation_intents WHERE run_id=%s", (run_id,)
        ).fetchone()
    if rejection:
        raise rejection
    return mutation_response(run, intent)


def mutation_response(run, intent) -> dict:
    response = intent["response"] or {}
    return {
        "data": response.get("data"),
        "source_revision": response.get("source_revision"),
        "mutation_status": intent["status"],
        "run_id": str(run["run_id"]),
        "sync_status": run["status"],
        "status_url": f"/v1/sync-runs/{run['run_id']}",
    }
