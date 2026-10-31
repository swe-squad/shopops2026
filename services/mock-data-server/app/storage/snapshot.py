"""Current native document versions are updated in the source write transaction."""

from psycopg import Connection, sql
from psycopg.types.json import Jsonb

from app.domain import (
    serialize_lazada,
    serialize_shopee,
    serialize_shopify,
    serialize_supplement,
)
from app.domain.entities import RESOURCES
from app.storage.db import connect

AS_OF = "2026-10-31T00:00:00+07:00"
RENDERERS = {
    "shopee-open-platform": serialize_shopee.render,
    "lazada": serialize_lazada.render,
    "shopify": serialize_shopify.render,
}


def data_rows(conn: Connection, *, retain_access: bool = False) -> dict[str, list[dict]]:
    result = {}
    for resource in RESOURCES.values():
        where = "" if retain_access and resource.admin else "WHERE deleted_at IS NULL"
        rows = conn.execute(
            sql.SQL("SELECT * FROM {} {} ORDER BY {}").format(
                sql.Identifier("mock", resource.table),
                sql.SQL(where),
                sql.SQL(",").join(map(sql.Identifier, resource.keys)),
            )
        ).fetchall()
        result[resource.table] = [
            resource.model.model_validate(
                {k: r[k] for k in resource.model.model_fields}
            ).model_dump(mode="json")
            for r in rows
        ]
    return result


def refresh(conn: Connection, revision: int) -> None:
    data = data_rows(conn)
    for shop in data["shops"]:
        scoped = {
            table: [r for r in rows if r.get("shop_key") == shop["shop_key"]]
            for table, rows in data.items()
        }
        payloads = RENDERERS[shop["platform"]](shop, scoped["orders"], scoped["order_items"])
        payloads["supplement"] = serialize_supplement.render(shop, scoped)
        for resource, payload in payloads.items():
            previous = conn.execute(
                "SELECT document FROM mock.document_versions WHERE shop_key=%s AND resource=%s",
                (shop["shop_key"], resource),
            ).fetchone()
            if previous and previous["document"]["payload"] == payload:
                continue
            kind = "api_subset"
            if resource == "supplement":
                kind = "demo_supplement"
            elif shop["platform"] == "shopee-open-platform":
                kind = "provisional_api_subset"
            document = {
                "document_id": f"{shop['platform']}/{shop['source_shop_id']}/{resource}/{revision}",
                "merchant_id": shop["merchant_id"],
                "platform": shop["platform"],
                "shop_id": shop["source_shop_id"],
                "resource": resource,
                "source_kind": kind,
                "captured_at": AS_OF,
                "resource_revision": revision,
                "payload": payload,
            }
            conn.execute(
                "INSERT INTO mock.document_versions VALUES (%s,%s,%s) "
                "ON CONFLICT (shop_key,resource) DO UPDATE SET document=EXCLUDED.document",
                (shop["shop_key"], resource, Jsonb(document)),
            )
    conn.execute(
        "DELETE FROM mock.document_versions WHERE shop_key NOT IN "
        "(SELECT shop_key FROM mock.shops WHERE deleted_at IS NULL)"
    )


def snapshot() -> dict:
    with connect() as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        revision = conn.execute("SELECT revision FROM mock.state").fetchone()["revision"]
        data = data_rows(conn, retain_access=True)
        documents = conn.execute(
            "SELECT document FROM mock.document_versions ORDER BY shop_key,resource"
        ).fetchall()
        tombstones = conn.execute("SELECT * FROM mock.tombstones ORDER BY tombstone_id").fetchall()
        for marker in tombstones:
            marker["deleted_at"] = marker["deleted_at"].isoformat()
        return {
            "schema_version": "1.0",
            "source_revision": revision,
            "complete": True,
            "as_of": AS_OF,
            "access": {r.table: data[r.table] for r in RESOURCES.values() if r.admin},
            "documents": [r["document"] for r in documents],
            "tombstones": tombstones,
            "counts": {r.name: len(data[r.table]) for r in RESOURCES.values()},
        }
