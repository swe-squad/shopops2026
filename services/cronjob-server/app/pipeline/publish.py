"""One transaction publishes a validated source revision and retains raw evidence."""

import hashlib
import json
from datetime import datetime

from psycopg import IntegrityError, sql
from psycopg.types.json import Jsonb

from app.api.common import APIError
from app.pipeline.normalize import invalid, key, normalize
from app.source.entities import RESOURCES
from app.storage.db import connect

ORDER = (
    "users",
    "merchants",
    "merchant-memberships",
    "shops",
    "products",
    "promotions",
    "orders",
    "order-items",
    "reviews",
    "returns",
    "inventory",
    "settlements",
    "fulfillment",
    "account-health",
)


def json_value(value):
    return json.loads(json.dumps(value, default=str))


def digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def upsert(conn, schema: str, table: str, rows: list[dict], keys: tuple) -> None:
    if not rows:
        return
    columns = list(rows[0])
    statement = sql.SQL("INSERT INTO {} ({}) VALUES ({}) ON CONFLICT ({}) DO UPDATE SET {}").format(
        sql.Identifier(schema, table),
        sql.SQL(",").join(map(sql.Identifier, columns)),
        sql.SQL(",").join(sql.Placeholder() for _ in columns),
        sql.SQL(",").join(map(sql.Identifier, keys)),
        sql.SQL(",").join(
            sql.SQL("{}=EXCLUDED.{}").format(sql.Identifier(c), sql.Identifier(c))
            for c in columns
            if c not in keys
        ),
    )
    with conn.cursor() as cursor:
        cursor.executemany(
            statement,
            [
                [
                    Jsonb(json_value(row[c])) if isinstance(row[c], (dict, list)) else row[c]
                    for c in columns
                ]
                for row in rows
            ],
        )


def immutable_document(conn, document: dict) -> None:
    data = dict(document)
    data["captured_at"] = datetime.fromisoformat(data["captured_at"])
    old = conn.execute(
        "SELECT * FROM raw.documents WHERE document_id=%s", (data["document_id"],)
    ).fetchone()
    if old:
        if old != data:
            raise APIError(422, "IMMUTABLE_DOCUMENT_CONFLICT")
        return
    upsert(conn, "raw", "documents", [data], ("document_id",))


def publish(value: dict, run_id=None, minimum_revision: int = 0) -> dict:
    normalized = normalize(value)
    snapshot = normalized["snapshot"]
    revision = snapshot["source_revision"]
    fingerprint = digest(value)
    counts = {}
    for resource in RESOURCES.values():
        if not resource.admin:
            for row in normalized["core"][resource.table]:
                counts.setdefault(row["shop_key"], {}).setdefault(resource.name, 0)
                counts[row["shop_key"]][resource.name] += 1
    try:
        with connect() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(8173603)")
            state = conn.execute("SELECT * FROM sync.state FOR UPDATE").fetchone()
            if revision < max(state["revision"], minimum_revision):
                raise APIError(422, "STALE_SOURCE_REVISION")
            unchanged = revision == state["revision"]
            if unchanged and fingerprint != state["snapshot_hash"]:
                raise APIError(422, "REVISION_CONTENT_CONFLICT")
            result = {
                "applied_source_revision": revision,
                "unchanged": unchanged,
                "shop_counts": counts,
            }
            if not unchanged:
                _apply(conn, normalized)
                conn.execute(
                    "UPDATE sync.state SET revision=%s,snapshot_hash=%s,last_run_id=%s",
                    (revision, fingerprint, run_id),
                )
            if run_id is not None:
                conn.execute(
                    "UPDATE sync.runs SET status='succeeded',finished_at=now(),"
                    "applied_revision=%s,result=%s,error_code=NULL,error_stage=NULL "
                    "WHERE run_id=%s",
                    (revision, Jsonb(result), run_id),
                )
            return result
    except IntegrityError:
        raise invalid() from None


def _apply(conn, normalized: dict) -> None:
    snapshot = normalized["snapshot"]
    for name in ORDER[:3]:
        resource = RESOURCES[name]
        old_rows = conn.execute(
            sql.SQL("SELECT * FROM {}").format(sql.Identifier("access", resource.table))
        ).fetchall()
        incoming = {key(resource, r) for r in normalized["access"][resource.table]}
        if any(key(resource, r) not in incoming for r in old_rows):
            raise APIError(422, "UNEXPLAINED_DELETION")
        upsert(conn, "access", resource.table, normalized["access"][resource.table], resource.keys)
    for document in snapshot["documents"]:
        immutable_document(conn, document)
    markers = {
        (m["resource"], key(RESOURCES[m["resource"]], m["record_key"])): m
        for m in snapshot["tombstones"]
    }
    # Child-first reconciliation. Missing rows require explicit deletion evidence.
    for name in reversed(ORDER[3:]):
        resource = RESOURCES[name]
        rows = normalized["core"][resource.table]
        new_keys = {key(resource, row) for row in rows}
        old_rows = conn.execute(
            sql.SQL("SELECT * FROM {}").format(sql.Identifier("core", resource.table))
        ).fetchall()
        for old in old_rows:
            old_key = key(resource, old)
            if old_key in new_keys:
                if resource.table == "shops":
                    new = next(r for r in rows if key(resource, r) == old_key)
                    if any(new[c] != old[c] for c in resource.immutable):
                        raise invalid()
                continue
            marker = markers.get((name, old_key))
            if marker is None:
                raise APIError(422, "UNEXPLAINED_DELETION")
            merchant = conn.execute(
                "SELECT merchant_id FROM core.shops WHERE shop_key=%s", (old["shop_key"],)
            ).fetchone()["merchant_id"]
            if marker["scope"]["merchant_id"] != merchant:
                raise invalid()
            conn.execute(
                sql.SQL("DELETE FROM {} WHERE {}").format(
                    sql.Identifier("core", resource.table),
                    sql.SQL(" AND ").join(
                        sql.SQL("{}=%s").format(sql.Identifier(c)) for c in resource.keys
                    ),
                ),
                old_key,
            )
    for marker in snapshot["tombstones"]:
        old = conn.execute(
            "SELECT * FROM sync.applied_deletions WHERE tombstone_id=%s", (marker["tombstone_id"],)
        ).fetchone()
        data = dict(marker)
        data["record_key"] = json_value(data["record_key"])
        data["deleted_at"] = datetime.fromisoformat(data["deleted_at"])
        if old and old != data:
            raise invalid()
        upsert(conn, "sync", "applied_deletions", [data], ("tombstone_id",))
        if not RESOURCES[marker["resource"]].admin:
            platform, shop_id = marker["scope"]["shop_key"].split(":", 1)
            immutable_document(
                conn,
                {
                    "document_id": f"deletion/{marker['tombstone_id']}",
                    "merchant_id": marker["scope"]["merchant_id"],
                    "platform": platform,
                    "shop_id": shop_id,
                    "resource": "deletion",
                    "source_kind": "demo_supplement",
                    "captured_at": marker["deleted_at"],
                    "resource_revision": marker["revision"],
                    "payload": json_value(marker),
                },
            )
    for name in ORDER[3:]:
        resource = RESOURCES[name]
        upsert(conn, "core", resource.table, normalized["core"][resource.table], resource.keys)
