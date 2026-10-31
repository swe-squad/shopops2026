"""Explicit, repeatable image backfill for the existing MVP demo catalog."""

import json
from pathlib import Path

from app.domain.entities import Product
from app.storage.db import connect
from app.storage.snapshot import refresh

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "mvp_base.json"


def backfill(*, apply: bool = False) -> dict[str, int]:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    matched = 0
    with connect() as conn:
        # Same lock as normal writes: rows, documents and revision commit together.
        revision = conn.execute(
            "SELECT revision FROM mock.state WHERE singleton FOR UPDATE"
        ).fetchone()["revision"]
        for platform, tables in fixture.items():
            for original in tables["products"]:
                product = Product.model_validate(original)
                if product.image_url is None:
                    continue
                for n in range(1, 8):
                    params = (
                        f"{platform}:{1000 + n}",
                        product.sku,
                        product.name,
                        product.cost_basis,
                        f"merchant-demo-{n:03}",
                    )
                    predicate = (
                        "p.shop_key=%s AND p.sku=%s AND p.name=%s AND p.cost_basis=%s "
                        "AND p.image_url IS NULL AND p.deleted_at IS NULL "
                        "AND EXISTS (SELECT 1 FROM mock.shops s WHERE s.shop_key=p.shop_key "
                        "AND s.merchant_id=%s AND s.deleted_at IS NULL)"
                    )
                    if apply:
                        matched += conn.execute(
                            "UPDATE mock.products p SET image_url=%s WHERE " + predicate,
                            (product.image_url, *params),
                        ).rowcount
                    else:
                        matched += conn.execute(
                            "SELECT count(*) n FROM mock.products p WHERE " + predicate, params
                        ).fetchone()["n"]
        if apply and matched:
            revision += 1
            refresh(conn, revision)
            conn.execute("UPDATE mock.state SET revision=%s WHERE singleton", (revision,))
    return {"matched": matched, "updated": matched if apply else 0, "source_revision": revision}
