import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.storage.migrations import migrate
from tests.test_catalog import PRODUCT, headers, prepare
from tests.test_shops import SHOP

ORDER = {
    "shop_key": SHOP["shop_key"],
    "order_id": "100072",
    "ordered_at": "2026-10-20T00:00:00+07:00",
    "updated_at": "2026-10-20T01:00:00+07:00",
    "currency": "VND",
    "status": "completed",
    "original_status": "COMPLETED",
    "seller_discount": "0.00",
    "platform_discount": "0.00",
    "promotion_id": None,
}
ITEM = {
    "shop_key": SHOP["shop_key"],
    "order_id": "100072",
    "line_id": "100:200",
    "sku": "SHIRT-M",
    "quantity": 2,
    "unit_price": "100000.00",
    "status": "completed",
}


def prepare_order(client):
    prepare(client)
    assert client.post("/v1/entities/products", json=PRODUCT, headers=headers()).status_code == 201
    result = client.post("/v1/entities/orders", json=ORDER, headers=headers())
    assert result.status_code == 201, result.text
    result = client.post("/v1/entities/order-items", json=ITEM, headers=headers())
    assert result.status_code == 201, result.text


def test_order_items_and_references(database):
    migrate()
    with TestClient(create_app()) as client:
        prepare_order(client)
        key = {"shop_key": SHOP["shop_key"], "order_id": "100072"}
        assert (
            client.get("/v1/entities/orders/record", params=key, headers=headers()).status_code
            == 200
        )
        response = client.get("/v1/entities/order-items", headers=headers())
        assert response.json()["data"][0]["quantity"] == 2
        assert response.json()["data"][0]["unit_price"] == "100000.00"
        assert (
            client.post(
                "/v1/entities/order-items",
                json=ITEM | {"line_id": "100:201", "sku": "MISSING"},
                headers=headers(),
            ).status_code
            == 409
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "shipped"},
        {"currency": "USD"},
        {"updated_at": "2026-10-19T00:00:00+07:00"},
    ],
)
def test_invalid_order_state(database, changes):
    migrate()
    with TestClient(create_app()) as client:
        prepare(client)
        response = client.post("/v1/entities/orders", json=ORDER | changes, headers=headers())
        assert response.status_code == 422


def test_native_item_status_and_parent_transition(database):
    migrate()
    with TestClient(create_app()) as client:
        prepare_order(client)
        item_key = {k: ITEM[k] for k in ("shop_key", "order_id", "line_id")}
        response = client.patch(
            "/v1/entities/order-items/record",
            params=item_key,
            json={"status": "open"},
            headers=headers(),
        )
        assert response.status_code == 422
        order_key = {k: ORDER[k] for k in ("shop_key", "order_id")}
        assert (
            client.patch(
                "/v1/entities/orders/record",
                params=order_key,
                json={"status": "shipped", "original_status": "SHIPPED"},
                headers=headers(),
            ).status_code
            == 200
        )
        result = client.get("/v1/entities/order-items/record", params=item_key, headers=headers())
        assert result.json()["data"]["status"] == "shipped"
