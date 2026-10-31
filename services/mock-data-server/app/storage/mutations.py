import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass

from psycopg import Connection
from psycopg.types.json import Jsonb

from app.api.common import APIError
from app.storage.db import connect
from app.storage.snapshot import refresh


@dataclass(frozen=True)
class Change:
    data: dict
    effective: bool = True


def mutate(
    actor: str, key: str, intent: dict, operation: Callable[[Connection, int], Change]
) -> dict:
    if not key or len(key) > 200:
        raise APIError(422, "INVALID_IDEMPOTENCY_KEY")
    digest = hashlib.sha256(
        json.dumps(intent, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    with connect() as conn:
        acquired = conn.execute(
            "SELECT pg_try_advisory_xact_lock(hashtextextended(%s,0)) AS ok",
            (json.dumps([actor, key]),),
        ).fetchone()["ok"]
        if not acquired:
            raise APIError(409, "MUTATION_IN_PROGRESS")
        row = conn.execute(
            "SELECT intent_hash,response FROM mock.receipts WHERE actor=%s AND idempotency_key=%s",
            (actor, key),
        ).fetchone()
        if row:
            if row["intent_hash"] != digest:
                raise APIError(409, "IDEMPOTENCY_KEY_REUSED")
            return row["response"]
        revision = (
            conn.execute("SELECT revision FROM mock.state WHERE singleton FOR UPDATE").fetchone()[
                "revision"
            ]
            + 1
        )
        change = operation(conn, revision)
        if change.effective:
            refresh(conn, revision)
            conn.execute("UPDATE mock.state SET revision=%s WHERE singleton", (revision,))
        else:
            revision -= 1
        response = {"data": change.data, "source_revision": revision}
        conn.execute(
            "INSERT INTO mock.receipts VALUES (%s,%s,%s,%s)",
            (actor, key, digest, Jsonb(response)),
        )
        return response
