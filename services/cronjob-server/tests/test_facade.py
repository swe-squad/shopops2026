from fastapi.testclient import TestClient

from app.main import create_app
from app.storage.db import connect
from app.storage.migrations import migrate


class FakeSource:
    calls = []

    def access(self, actor):
        return {"user_id": actor, "merchant_ids": ["m1"], "shop_keys": ["lazada:1001"]}

    def request(self, method, path, **kwargs):
        with connect() as conn:
            assert conn.execute("SELECT count(*) n FROM sync.mutation_intents").fetchone()["n"] == 1
        self.calls.append((method, path, kwargs))
        return {"data": kwargs["body"], "source_revision": 1}


def test_facade_persists_before_forward_and_replay_does_not_write_twice(database):
    migrate()
    source = FakeSource()
    app = create_app(source=source, start_worker=False)
    with TestClient(app) as client:
        body = {
            "shop_key": "lazada:1001",
            "sku": "NEW",
            "name": "new",
            "unit_cost": "1.00",
            "cost_basis": "demo",
        }
        headers = {"X-Demo-User-Id": "+84900000001", "Idempotency-Key": "new-product"}
        first = client.post("/v1/mock/products", json=body, headers=headers)
        assert first.status_code == 202, first.text
        replay = client.post("/v1/mock/products", json=body, headers=headers)
        assert replay.json()["run_id"] == first.json()["run_id"]
        assert len(source.calls) == 1
        denied = client.post(
            "/v1/mock/products", json=body | {"shop_key": "lazada:other"}, headers=headers
        )
        assert denied.status_code == 404
