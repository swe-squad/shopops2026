from fastapi.testclient import TestClient

from app.main import create_app
from app.storage.migrations import migrate
from tests.test_catalog import headers
from tests.test_orders import prepare_order
from tests.test_shops import SHOP


def test_snapshot_versions_change_only_with_their_resource(database):
    migrate()
    with TestClient(create_app()) as client:
        prepare_order(client)
        first = client.get("/v1/snapshot")
        assert first.status_code == 200
        first = first.json()
        assert first["complete"] is True
        assert first["counts"]["orders"] == 1
        assert first["counts"]["order-items"] == 1
        assert first == client.get("/v1/snapshot").json()
        before = {d["resource"]: d for d in first["documents"]}
        assert (
            client.patch(
                "/v1/entities/products/record",
                params={"shop_key": SHOP["shop_key"], "sku": "SHIRT-M"},
                json={"unit_cost": "60000.00"},
                headers=headers(),
            ).status_code
            == 200
        )
        second = client.get("/v1/snapshot").json()
        after = {d["resource"]: d for d in second["documents"]}
        assert second["source_revision"] > first["source_revision"]
        assert before["orders"] == after["orders"]
        assert before["supplement"]["document_id"] != after["supplement"]["document_id"]
        assert after["supplement"]["payload"]["products"][0]["unit_cost"] == "60000.00"
        assert second["as_of"] == "2026-10-31T00:00:00+07:00"
