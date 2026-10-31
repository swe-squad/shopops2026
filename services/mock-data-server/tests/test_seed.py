from fastapi.testclient import TestClient

from app.main import create_app
from app.storage.migrations import migrate
from app.storage.seed import seed
from tests.test_catalog import headers


def test_seed_counts_shared_visibility_and_no_reset(database):
    migrate()
    assert seed() == {"seeded": True}
    with TestClient(create_app()) as client:
        snapshot = client.get("/v1/snapshot").json()
        assert snapshot["counts"]["users"] == 10
        assert snapshot["counts"]["merchants"] == 7
        assert snapshot["counts"]["shops"] == 21
        assert snapshot["counts"]["orders"] == 140
        visible = {}
        for n in range(1, 11):
            phone = f"+849000000{n:02}"
            result = client.get("/v1/entities/orders", headers={"X-Demo-User-Id": phone}).json()
            assert result["pagination"]["total"] == 20
            visible[n] = {(r["shop_key"], r["order_id"]) for r in result["data"]}
        assert visible[5] == visible[6]
        assert visible[7] == visible[8]
        assert visible[9] == visible[10]
        assert not visible[1] & visible[2]
        key = {"shop_key": "shopee-open-platform:1001", "sku": "SHIRT-M"}
        response = client.patch(
            "/v1/entities/products/record",
            params=key,
            json={"name": "Preserve edit"},
            headers=headers(),
        )
        assert response.status_code == 200
        assert seed() == {"seeded": False}
        assert (
            client.get("/v1/entities/products/record", params=key, headers=headers()).json()[
                "data"
            ]["name"]
            == "Preserve edit"
        )
