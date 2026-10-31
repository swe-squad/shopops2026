from uuid import uuid4

from fastapi.testclient import TestClient

from app.domain.entities import Shop
from app.main import create_app
from app.storage.migrations import migrate
from tests.test_access import PHONE, post

SHOP = {
    "shop_key": "shopee-open-platform:1001",
    "merchant_id": "m1",
    "platform": "shopee-open-platform",
    "source_shop_id": "1001",
    "name": "Demo",
    "currency": "VND",
    "timezone": "Asia/Ho_Chi_Minh",
    "capabilities": {"orders": True, "account_health": True},
}


def test_existing_capability_provenance_strings_are_preserved():
    value = SHOP | {"capabilities": {"orders": "provisional", "account_health": "demo_supplement"}}
    assert Shop.model_validate(value).capabilities == value["capabilities"]


def setup_access(client):
    for phone in [PHONE, "+84900000002", "+84900000003"]:
        assert post(client, "users", {"user_id": phone, "display_name": "Demo"}).status_code == 201
    assert post(client, "merchants", {"merchant_id": "m1", "name": "Merchant"}).status_code == 201
    for phone in [PHONE, "+84900000002"]:
        assert (
            post(
                client,
                "merchant-memberships",
                {
                    "user_id": phone,
                    "merchant_id": "m1",
                    "role": "viewer",
                },
            ).status_code
            == 201
        )


def test_shop_crud_shared_scope_and_immutable_ownership(database):
    migrate()
    with TestClient(create_app()) as client:
        setup_access(client)
        headers = {"X-Demo-User-Id": PHONE, "Idempotency-Key": str(uuid4())}
        assert client.post("/v1/entities/shops", json=SHOP, headers=headers).status_code == 201
        for phone, expected in [(PHONE, 1), ("+84900000002", 1), ("+84900000003", 0)]:
            result = client.get("/v1/entities/shops", headers={"X-Demo-User-Id": phone})
            assert result.json()["pagination"]["total"] == expected
        assert client.get("/v1/access", params={"user_id": PHONE}).json()["shop_keys"] == [
            SHOP["shop_key"]
        ]
        assert (
            client.patch(
                "/v1/entities/shops/record",
                params={"shop_key": SHOP["shop_key"]},
                json={"merchant_id": "other"},
                headers=headers,
            ).status_code
            == 422
        )
        bad = SHOP | {"shop_key": "wrong"}
        assert client.post("/v1/entities/shops", json=bad, headers=headers).status_code == 422
        assert (
            client.get(
                "/v1/entities/shops/record",
                params={"shop_key": SHOP["shop_key"]},
                headers={"X-Demo-User-Id": "+84900000003"},
            ).status_code
            == 404
        )


def test_replaying_mutation_does_not_bypass_current_membership(database):
    migrate()
    with TestClient(create_app()) as client:
        setup_access(client)
        headers = {"X-Demo-User-Id": PHONE, "Idempotency-Key": "create-shop"}
        assert client.post("/v1/entities/shops", json=SHOP, headers=headers).status_code == 201
        assert (
            client.delete(
                "/v1/admin/entities/merchant-memberships/record",
                params={"user_id": PHONE, "merchant_id": "m1"},
                headers={"Idempotency-Key": str(uuid4())},
            ).status_code
            == 200
        )
        assert client.post("/v1/entities/shops", json=SHOP, headers=headers).status_code == 404


def test_replay_patch_and_delete_rechecks_membership(database):
    migrate()
    with TestClient(create_app()) as client:
        setup_access(client)
        create_headers = {"X-Demo-User-Id": PHONE, "Idempotency-Key": "create"}
        assert (
            client.post("/v1/entities/shops", json=SHOP, headers=create_headers).status_code == 201
        )
        path = "/v1/entities/shops/record"
        key = {"shop_key": SHOP["shop_key"]}
        patch_headers = {"X-Demo-User-Id": PHONE, "Idempotency-Key": "patch"}
        delete_headers = {"X-Demo-User-Id": PHONE, "Idempotency-Key": "delete"}
        assert (
            client.patch(path, params=key, json={"name": "New"}, headers=patch_headers).status_code
            == 200
        )
        assert client.delete(path, params=key, headers=delete_headers).status_code == 200
        assert (
            client.delete(
                "/v1/admin/entities/merchant-memberships/record",
                params={"user_id": PHONE, "merchant_id": "m1"},
                headers={"Idempotency-Key": str(uuid4())},
            ).status_code
            == 200
        )
        assert (
            client.patch(path, params=key, json={"name": "New"}, headers=patch_headers).status_code
            == 404
        )
        assert client.delete(path, params=key, headers=delete_headers).status_code == 404
