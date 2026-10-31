import pytest
from psycopg import IntegrityError

from app.api.common import APIError
from app.pipeline.normalize import normalize
from app.pipeline.publish import publish
from app.source.entities import RESOURCES
from app.storage.db import connect
from app.storage.migrations import migrate
from tests.test_normalization import full_snapshot


def deleted_order_snapshot():
    value = full_snapshot()
    normalized = normalize(value)
    shop = "shopee-open-platform:1001"
    order = next(r for r in normalized["core"]["orders"] if r["shop_key"] == shop)
    oid = order["order_id"]
    value["source_revision"] = 2
    for name, resource in RESOURCES.items():
        if resource.admin:
            continue
        for row in normalized["core"][resource.table]:
            if row.get("order_id") == oid and row["shop_key"] == shop:
                value["tombstones"].append(
                    {
                        "tombstone_id": len(value["tombstones"]) + 1,
                        "revision": 2,
                        "resource": name,
                        "record_key": resource.model.model_validate(
                            {k: v for k, v in row.items() if k in resource.model.model_fields}
                        ).model_dump(mode="json", include=set(resource.keys)),
                        "scope": {
                            "shop_key": shop,
                            "merchant_id": value["documents"][0]["merchant_id"],
                        },
                        "deleted_at": "2026-10-31T00:00:00+07:00",
                    }
                )
                value["counts"][name] -= 1
    for doc in value["documents"]:
        if doc["platform"] != "shopee-open-platform" or doc["shop_id"] != "1001":
            continue
        doc["document_id"] += "/2"
        doc["resource_revision"] = 2
        if doc["resource"] == "orders":
            rows = doc["payload"]["response"]["order_list"]
            doc["payload"]["response"]["order_list"] = [r for r in rows if r["order_sn"] != oid]
        else:
            for name, rows in doc["payload"].items():
                if isinstance(rows, list):
                    doc["payload"][name] = [r for r in rows if str(r.get("order_id")) != oid]
    return value, shop, oid


def test_cascade_delete_retains_history_and_recalculates_views(database):
    migrate()
    publish(full_snapshot())
    value, shop, oid = deleted_order_snapshot()
    publish(value)
    assert publish(value)["unchanged"]
    with connect() as conn:
        assert conn.execute("SELECT count(*) n FROM core.orders").fetchone()["n"] == 1343
        assert not conn.execute(
            "SELECT 1 FROM mart.order_economics WHERE shop_key=%s AND order_id=%s", (shop, oid)
        ).fetchone()
        assert conn.execute("SELECT count(*) n FROM raw.documents").fetchone()["n"] == 11 + len(
            value["tombstones"]
        )


def test_missing_row_without_marker_rolls_back(database):
    migrate()
    publish(full_snapshot())
    value, _, _ = deleted_order_snapshot()
    value["tombstones"] = []
    with pytest.raises(APIError, match="Unexplained deletion"):
        publish(value)
    with connect() as conn:
        assert conn.execute("SELECT count(*) n FROM raw.documents").fetchone()["n"] == 9


def test_late_database_failure_rolls_back_every_schema(database, monkeypatch):
    from app.pipeline import publish as module

    migrate()
    original = module.upsert

    def broken(conn, schema, table, rows, keys):
        original(conn, schema, table, rows, keys)
        if table == "fulfillment":
            raise IntegrityError("simulated constraint failure")

    monkeypatch.setattr(module, "upsert", broken)
    with pytest.raises(APIError):
        publish(full_snapshot())
    with connect() as conn:
        for relation in ("core.orders", "raw.documents", "access.users"):
            assert conn.execute(f"SELECT count(*) n FROM {relation}").fetchone()["n"] == 0
        assert conn.execute("SELECT revision FROM sync.state").fetchone()["revision"] == -1
