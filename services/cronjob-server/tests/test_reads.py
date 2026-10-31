from fastapi.testclient import TestClient

from app.api.common import APIError
from app.api.reads import MARTS
from app.main import create_app
from app.pipeline.publish import publish
from app.storage.migrations import migrate
from tests.test_normalization import full_snapshot


class Grants:
    allowed = True
    unavailable = False

    def access(self, actor):
        if self.unavailable:
            raise APIError(503, "SOURCE_UNAVAILABLE")
        if not self.allowed:
            raise APIError(403, "ACCESS_DENIED")
        snapshot = full_snapshot()
        doc = next(d for d in snapshot["documents"] if d["platform"] == "lazada")
        return {
            "user_id": actor,
            "merchant_ids": [doc["merchant_id"]],
            "shop_keys": ["lazada:1001"],
        }


def test_core_marts_raw_scope_and_immediate_revocation(database):
    migrate()
    publish(full_snapshot())
    source = Grants()
    with TestClient(create_app(source=source, start_worker=False)) as client:
        headers = {"X-Demo-User-Id": "+84900000001"}
        paths = ["/v1/core/orders", "/v1/raw/documents", *[f"/v1/marts/{v}" for v in MARTS]]
        for path in paths:
            response = client.get(path, headers=headers)
            assert response.status_code == 200, response.text
            data = response.json()
            assert data["applied_source_revision"] == 1
            assert data["data"], path
            assert all(
                r.get("shop_key", f"{r.get('platform')}:{r.get('shop_id')}") == "lazada:1001"
                for r in data["data"]
            )
        assert (
            client.get(
                "/v1/core/orders/record",
                params={"shop_key": "shopify:1001", "order_id": "gid://shopify/Order/100000"},
                headers=headers,
            ).status_code
            == 404
        )
        assert (
            client.get(
                "/v1/core/orders", params={"order_by": "1;DROP TABLE core.orders"}, headers=headers
            ).status_code
            == 422
        )
        source.allowed = False
        for path in paths:
            assert client.get(path, headers=headers).status_code == 403
        source.unavailable = True
        assert client.get("/v1/core/orders", headers=headers).status_code == 503


def test_settings_validation_idempotency_and_clock(database):
    migrate()
    with TestClient(create_app(source=Grants(), start_worker=False)) as client:
        path = "/v1/admin/mart-settings"
        headers = {"Idempotency-Key": "settings"}
        assert client.patch(path, json={"recent_days": 0}, headers=headers).status_code == 422
        response = client.patch(path, json={"recent_days": 3}, headers=headers)
        assert response.status_code == 200
        assert response.json()["recent_days"] == 3
        assert (
            client.patch(path, json={"recent_days": 3}, headers=headers).json() == response.json()
        )
        assert client.patch(path, json={"recent_days": 4}, headers=headers).status_code == 409
        assert (
            client.patch(
                path, json={"as_of": None}, headers={"Idempotency-Key": "null"}
            ).status_code
            == 422
        )
