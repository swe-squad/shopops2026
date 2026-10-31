from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.main import create_app
from app.storage.migrations import migrate
from app.storage.seed import seed


def test_snapshot_is_coherent_while_crud_commits(database):
    migrate()
    seed()
    with TestClient(create_app()) as client:

        def change():
            return client.patch(
                "/v1/entities/products/record",
                params={"shop_key": "lazada:1001", "sku": "SHIRT-M"},
                json={"name": "Concurrent edit"},
                headers={"X-Demo-User-Id": "+84900000001", "Idempotency-Key": "concurrent"},
            )

        before = client.get("/v1/snapshot").json()
        with ThreadPoolExecutor(max_workers=2) as pool:
            mutation = pool.submit(change)
            snapshot = pool.submit(lambda: client.get("/v1/snapshot").json()).result()
            assert mutation.result().status_code == 200
        after = client.get("/v1/snapshot").json()
        assert snapshot in (before, after)
        assert after["source_revision"] == before["source_revision"] + 1
