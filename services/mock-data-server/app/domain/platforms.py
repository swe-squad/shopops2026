"""Validation and aggregation of source-specific order semantics."""

import re

from app.api.common import APIError

SHOPEE = {
    "COMPLETED": "completed",
    "READY_TO_SHIP": "open",
    "PROCESSED": "open",
    "SHIPPED": "shipped",
    "CANCELLED": "cancelled",
}
LAZADA = {
    "delivered": "completed",
    "pending": "open",
    "packed": "open",
    "ready_to_ship": "open",
    "shipped": "shipped",
    "canceled": "cancelled",
}
LAZADA_NATIVE = {
    "completed": "delivered",
    "open": "pending",
    "shipped": "shipped",
    "cancelled": "canceled",
    "unknown": "unknown",
}


def validate(conn, table: str, value: dict) -> None:
    if table not in {"orders", "order_items"}:
        return
    shop = conn.execute(
        "SELECT * FROM mock.shops WHERE shop_key=%s", (value["shop_key"],)
    ).fetchone()
    platform = shop["platform"]
    if table == "orders":
        if value["currency"] != shop["currency"]:
            raise APIError(422, "CURRENCY_MISMATCH")
        status = value["status"]
        original = value["original_status"]
        if platform == "shopee-open-platform":
            expected = SHOPEE.get(original, "unknown")
        elif platform == "shopify":
            if not value["order_id"].startswith("gid://shopify/Order/"):
                raise APIError(422, "INVALID_SOURCE_ID")
            expected = (
                "cancelled"
                if status == "cancelled"
                else {"FULFILLED": "shipped", "UNFULFILLED": "open"}.get(original, "unknown")
            )
        else:
            states = {LAZADA.get(part, "unknown") for part in original.split(",")}
            expected = next(iter(states)) if len(states) == 1 else "mixed"
            existing = conn.execute(
                "SELECT status,native_status FROM mock.order_items "
                "WHERE shop_key=%s AND order_id=%s "
                "AND deleted_at IS NULL",
                (value["shop_key"], value["order_id"]),
            ).fetchall()
            if existing:
                states = {r["status"] for r in existing}
                expected = next(iter(states)) if len(states) == 1 else "mixed"
                native = {r["native_status"] or LAZADA_NATIVE[r["status"]] for r in existing}
                if set(original.split(",")) != native:
                    raise APIError(422, "STATUS_MISMATCH")
        if status != expected:
            raise APIError(422, "STATUS_MISMATCH")
    else:
        if platform != "lazada":
            parent = conn.execute(
                "SELECT status FROM mock.orders WHERE shop_key=%s AND order_id=%s",
                (value["shop_key"], value["order_id"]),
            ).fetchone()
            if value["status"] != parent["status"] or value.get("native_status") is not None:
                raise APIError(422, "STATUS_MISMATCH")
        if platform == "lazada" and value["quantity"] != 1:
            raise APIError(422, "LAZADA_UNIT_QUANTITY_REQUIRED")
        if platform == "shopee-open-platform" and not re.fullmatch(r"\d+:\d+", value["line_id"]):
            raise APIError(422, "INVALID_SOURCE_LINE_ID")
        if platform == "shopify" and not value["line_id"].startswith("gid://shopify/LineItem/"):
            raise APIError(422, "INVALID_SOURCE_LINE_ID")
        if platform == "lazada" and value["native_status"] is not None:
            if LAZADA.get(value["native_status"], "unknown") != value["status"]:
                raise APIError(422, "STATUS_MISMATCH")


def aggregate(conn, table: str, value: dict) -> None:
    if table == "orders" and not value["shop_key"].startswith("lazada:"):
        conn.execute(
            "UPDATE mock.order_items SET status=%s WHERE shop_key=%s AND order_id=%s "
            "AND deleted_at IS NULL",
            (value["status"], value["shop_key"], value["order_id"]),
        )
    if table != "order_items" or not value["shop_key"].startswith("lazada:"):
        return
    items = conn.execute(
        "SELECT status,native_status FROM mock.order_items "
        "WHERE shop_key=%s AND order_id=%s AND deleted_at IS NULL",
        (value["shop_key"], value["order_id"]),
    ).fetchall()
    states = {r["status"] for r in items}
    status = next(iter(states)) if len(states) == 1 else ("mixed" if states else "unknown")
    original = (
        ",".join(sorted({r["native_status"] or LAZADA_NATIVE[r["status"]] for r in items}))
        or "unknown"
    )
    conn.execute(
        "UPDATE mock.orders SET status=%s,original_status=%s WHERE shop_key=%s AND order_id=%s",
        (status, original, value["shop_key"], value["order_id"]),
    )
