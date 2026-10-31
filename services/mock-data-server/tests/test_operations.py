import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.storage.migrations import migrate
from tests.test_catalog import headers
from tests.test_orders import prepare_order
from tests.test_shops import SHOP

BASE = {"shop_key": SHOP["shop_key"]}
CASES = [
    (
        "reviews",
        BASE
        | {
            "review_id": "r1",
            "order_id": "100072",
            "sku": "SHIRT-M",
            "reviewed_at": "2026-10-30T12:00:00+07:00",
            "rating": 1,
            "body": "Size too small",
        },
        ("review_id",),
        {"rating": 2},
    ),
    (
        "returns",
        BASE
        | {
            "return_id": "t1",
            "order_id": "100072",
            "requested_at": "2026-10-30T12:00:00+07:00",
            "reason": "Size",
            "status": "approved",
            "refund_amount": "100000.00",
        },
        ("return_id",),
        {"status": "completed"},
    ),
    (
        "inventory",
        BASE
        | {
            "sku": "SHIRT-M",
            "location_id": "default",
            "observed_at": "2026-10-30T12:00:00+07:00",
            "available": 2,
        },
        ("sku", "location_id", "observed_at"),
        {"available": None},
    ),
    (
        "settlements",
        BASE
        | {
            "order_id": "100072",
            "fee_amount": "5000.00",
            "seller_shipping_cost": "0.00",
            "refund_amount": "0.00",
            "actual_payout": "195000.00",
            "paid_at": "2026-10-30T12:00:00+07:00",
        },
        ("order_id",),
        {"actual_payout": None},
    ),
    (
        "fulfillment",
        BASE
        | {
            "order_id": "100072",
            "ship_by": "2026-10-30T12:00:00+07:00",
            "shipped_at": None,
            "deadline_basis": "demo",
        },
        ("order_id",),
        {"shipped_at": "2026-10-30T10:00:00+07:00"},
    ),
    (
        "account-health",
        BASE
        | {
            "event_id": "e1",
            "occurred_at": "2026-10-30T00:00:00+07:00",
            "expires_at": "2026-11-30T00:00:00+07:00",
            "penalty_points": 3,
            "reason": "Demo",
        },
        ("event_id",),
        {"penalty_points": 2},
    ),
]


@pytest.mark.parametrize("resource,value,key_fields,changes", CASES, ids=[c[0] for c in CASES])
def test_complete_business_crud(database, resource, value, key_fields, changes):
    migrate()
    with TestClient(create_app()) as client:
        prepare_order(client)
        path = f"/v1/entities/{resource}"
        created = client.post(path, json=value, headers=headers())
        assert created.status_code == 201, created.text
        keys = BASE | {k: value[k] for k in key_fields}
        read = client.get(path + "/record", params=keys, headers=headers())
        assert read.status_code == 200
        changed = client.patch(path + "/record", params=keys, json=changes, headers=headers())
        assert changed.status_code == 200, changed.text
        for key, expected in changes.items():
            if key != "shipped_at":
                assert changed.json()["data"][key] == expected
        removed = client.delete(path + "/record", params=keys, headers=headers())
        assert removed.status_code == 200, removed.text
        assert client.get(path + "/record", params=keys, headers=headers()).status_code == 404
        assert client.post(path, json=value, headers=headers()).status_code == 409
