from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import create_app
from app.storage.migrations import migrate

PHONE = "+84900000001"


def post(client, resource, data, key=None):
    return client.post(
        f"/v1/admin/entities/{resource}",
        json=data,
        headers={"Idempotency-Key": key or str(uuid4())},
    )


def test_access_crud_and_current_membership(database):
    migrate()
    with TestClient(create_app()) as client:
        assert post(client, "users", {"user_id": PHONE, "display_name": "Demo"}).status_code == 201
        assert (
            post(client, "merchants", {"merchant_id": "m1", "name": "Shop owner"}).status_code
            == 201
        )
        membership = {"user_id": PHONE, "merchant_id": "m1", "role": "owner"}
        assert post(client, "merchant-memberships", membership).status_code == 201
        assert client.get("/v1/access", params={"user_id": PHONE}).json()["merchant_ids"] == ["m1"]
        changed = client.patch(
            "/v1/admin/entities/users/record",
            params={"user_id": PHONE},
            json={"display_name": "Changed"},
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert changed.status_code == 200
        assert changed.json()["data"]["user_id"] == PHONE
        assert changed.json()["data"]["display_name"] == "Changed"
        assert (
            client.delete(
                "/v1/admin/entities/users/record",
                params={"user_id": PHONE},
                headers={"Idempotency-Key": str(uuid4())},
            ).status_code
            == 409
        )
        assert (
            client.delete(
                "/v1/admin/entities/merchant-memberships/record",
                params=membership | {},
                headers={"Idempotency-Key": str(uuid4())},
            ).status_code
            == 422
        )
        assert (
            client.delete(
                "/v1/admin/entities/merchant-memberships/record",
                params={"user_id": PHONE, "merchant_id": "m1"},
                headers={"Idempotency-Key": str(uuid4())},
            ).status_code
            == 200
        )
        assert client.get("/v1/access", params={"user_id": PHONE}).json()["merchant_ids"] == []


def test_access_input_and_receipt_contract(database):
    migrate()
    with TestClient(create_app()) as client:
        data = {"user_id": PHONE, "display_name": "Demo"}
        first = post(client, "users", data, "same")
        assert first.status_code == 201
        assert post(client, "users", data, "same").json() == first.json()
        assert post(client, "users", data | {"display_name": "Other"}, "same").status_code == 409
        assert post(client, "users", data | {"user_id": "invalid"}).status_code == 422
        assert post(client, "users", data | {"role": "owner"}).status_code == 422
        assert client.get("/v1/access", params={"user_id": "+84900000999"}).status_code == 403
        assert client.get("/v1/admin/entities/users").json()["pagination"]["total"] == 1
