"""Offline catalog HTTP fixture using the actual mock-source seed, never production data."""

from copy import deepcopy
import json
from pathlib import Path

import httpx


class FixtureCatalog:
    def __init__(self):
        seed = Path(__file__).resolve().parents[2] / (
            "services/mock-data-server/app/fixtures/mvp_base.json"
        )
        self.records = deepcopy(json.loads(seed.read_text())["shopee-open-platform"])
        self.revision = 1
        self.shop_key = "shopee-open-platform:1001"

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if (
            request.url.host != "catalog.test"
            or request.method != "GET"
            or request.headers.get("X-Demo-User-Id") != "+84900000001"
        ):
            return httpx.Response(403, json={"detail": "Fixture access denied"})
        resource = request.url.path.removeprefix("/v1/mock/").replace("-", "_")
        if resource not in self.records:
            return httpx.Response(404, json={"detail": "Fixture resource missing"})
        rows = self.records[resource]
        requested_shop = request.url.params.get("shop_key")
        if requested_shop:
            rows = [row for row in rows if row.get("shop_key") == requested_shop]
        limit = int(request.url.params.get("limit", "200"))
        offset = int(request.url.params.get("offset", "0"))
        return httpx.Response(200, json={
            "data": rows[offset:offset + limit],
            "pagination": {"limit": limit, "offset": offset, "total": len(rows)},
            "source_revision": self.revision,
        })

    def set_stock(self, available: int) -> None:
        rows = [row for row in self.records["inventory"] if row["sku"] == "SHIRT-M"]
        latest = max(rows, key=lambda row: row["observed_at"])
        latest["available"] = available
        self.revision += 1
