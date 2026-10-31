from fastapi.testclient import TestClient

from app.main import create_app
from app.storage.migrations import migrate
from tests.test_catalog import headers
from tests.test_operations import CASES
from tests.test_orders import ORDER, prepare_order
from tests.test_shops import SHOP


def test_order_delete_cascades_explicit_markers_once(database):
    migrate()
    with TestClient(create_app()) as client:
        prepare_order(client)
        for resource, value, _, _ in CASES:
            if resource in {"reviews", "returns", "settlements", "fulfillment"}:
                assert (
                    client.post(
                        f"/v1/entities/{resource}", json=value, headers=headers()
                    ).status_code
                    == 201
                )
        key = {"shop_key": SHOP["shop_key"], "order_id": ORDER["order_id"]}
        h = headers()
        first = client.delete("/v1/entities/orders/record", params=key, headers=h)
        assert first.status_code == 200, first.text
        assert (
            client.delete("/v1/entities/orders/record", params=key, headers=h).json()
            == first.json()
        )
        snap = client.get("/v1/snapshot").json()
        expected = {"orders", "order-items", "reviews", "returns", "settlements", "fulfillment"}
        assert {t["resource"] for t in snap["tombstones"]} == expected
        assert {t["revision"] for t in snap["tombstones"]} == {first.json()["source_revision"]}
        assert all(snap["counts"][name] == 0 for name in expected)
        assert snap["counts"]["products"] == 1
        assert client.post("/v1/entities/orders", json=ORDER, headers=headers()).status_code == 409


def test_referenced_product_delete_rolls_back_without_markers(database):
    migrate()
    with TestClient(create_app()) as client:
        prepare_order(client)
        before = client.get("/v1/snapshot").json()
        response = client.delete(
            "/v1/entities/products/record",
            params={"shop_key": SHOP["shop_key"], "sku": "SHIRT-M"},
            headers=headers(),
        )
        assert response.status_code == 409
        assert client.get("/v1/snapshot").json() == before
