from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import create_app
from app.storage.migrations import migrate
from tests.test_access import PHONE
from tests.test_shops import SHOP, setup_access

PRODUCT = {
    "shop_key": SHOP["shop_key"],
    "sku": "SHIRT-M",
    "name": "Shirt",
    "unit_cost": "50000.00",
    "cost_basis": "demo",
}
PROMOTION = {
    "shop_key": SHOP["shop_key"],
    "promotion_id": "SALE",
    "name": "Sale",
    "funding": "seller",
    "starts_at": "2026-10-17T00:00:00+07:00",
    "ends_at": "2026-11-01T00:00:00+07:00",
}


def headers():
    return {"X-Demo-User-Id": PHONE, "Idempotency-Key": str(uuid4())}


def prepare(client):
    setup_access(client)
    assert client.post("/v1/entities/shops", json=SHOP, headers=headers()).status_code == 201


def test_catalog_money_nulls_and_crud(database):
    migrate()
    with TestClient(create_app()) as client:
        prepare(client)
        for resource, value, key in [
            ("products", PRODUCT, {"shop_key": SHOP["shop_key"], "sku": "SHIRT-M"}),
            ("promotions", PROMOTION, {"shop_key": SHOP["shop_key"], "promotion_id": "SALE"}),
        ]:
            assert (
                client.post(f"/v1/entities/{resource}", json=value, headers=headers()).status_code
                == 201
            )
            assert (
                client.get(
                    f"/v1/entities/{resource}/record", params=key, headers=headers()
                ).status_code
                == 200
            )
            assert (
                client.patch(
                    f"/v1/entities/{resource}/record",
                    params=key,
                    json={"name": "Changed"},
                    headers=headers(),
                ).json()["data"]["name"]
                == "Changed"
            )
        key = {"shop_key": SHOP["shop_key"], "sku": "SHIRT-M"}
        response = client.patch(
            "/v1/entities/products/record",
            params=key,
            json={"unit_cost": None},
            headers=headers(),
        )
        assert response.json()["data"]["unit_cost"] is None
        assert (
            client.delete("/v1/entities/products/record", params=key, headers=headers()).status_code
            == 200
        )
        assert (
            client.post("/v1/entities/products", json=PRODUCT, headers=headers()).status_code == 409
        )


def test_invalid_catalog_values(database):
    migrate()
    with TestClient(create_app()) as client:
        prepare(client)
        assert (
            client.post(
                "/v1/entities/products",
                json=PRODUCT | {"unit_cost": "-0.01"},
                headers=headers(),
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/v1/entities/promotions",
                json=PROMOTION | {"ends_at": PROMOTION["starts_at"]},
                headers=headers(),
            ).status_code
            == 422
        )
