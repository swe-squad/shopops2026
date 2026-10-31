"""Explicit, non-destructive seeding of synthetic demo entities."""

import json
from pathlib import Path

from psycopg import sql

from app.api.common import APIError
from app.domain.entities import RESOURCES
from app.storage.db import connect
from app.storage.entities import save
from app.storage.snapshot import refresh

ORDER = (
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


def seed() -> dict:
    fixture = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "mvp_base.json").read_text(
            encoding="utf-8"
        )
    )
    with connect() as conn:
        state = conn.execute("SELECT * FROM mock.state WHERE singleton FOR UPDATE").fetchone()
        if state["seeded"]:
            return {"seeded": False}
        if any(
            conn.execute(
                sql.SQL("SELECT 1 FROM {} LIMIT 1").format(sql.Identifier("mock", r.table))
            ).fetchone()
            for r in RESOURCES.values()
        ):
            raise APIError(409, "SEED_REQUIRES_EMPTY_SOURCE")
        for n in range(1, 11):
            save(
                conn,
                RESOURCES["users"],
                {
                    "user_id": f"+849000000{n:02}",
                    "display_name": f"Demo user {n}",
                    "is_active": True,
                },
            )
        for n in range(1, 8):
            merchant_id = f"merchant-demo-{n:03}"
            save(
                conn,
                RESOURCES["merchants"],
                {
                    "merchant_id": merchant_id,
                    "name": f"Demo merchant {n}",
                    "is_active": True,
                },
            )
            users = [n] if n <= 4 else [2 * n - 5, 2 * n - 4]
            for number in users:
                save(
                    conn,
                    RESOURCES["merchant-memberships"],
                    {
                        "user_id": f"+849000000{number:02}",
                        "merchant_id": merchant_id,
                        "role": "owner" if number == users[0] else "viewer",
                        "is_active": True,
                    },
                )
            for platform, tables in fixture.items():
                shop_id = str(1000 + n)
                shop_key = f"{platform}:{shop_id}"
                for name in ORDER:
                    resource = RESOURCES[name]
                    for original in tables[resource.table]:
                        value = original | {"shop_key": shop_key}
                        if name == "shops":
                            value |= {"source_shop_id": shop_id, "merchant_id": merchant_id}
                        value = resource.model.model_validate(value).model_dump()
                        save(conn, resource, value)
        revision = state["revision"] + 1
        refresh(conn, revision)
        conn.execute("UPDATE mock.state SET seeded=true, revision=%s WHERE singleton", (revision,))
    return {"seeded": True}
