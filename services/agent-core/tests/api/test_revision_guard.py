"""Conversation creation binds its expected revision in the repository transaction."""

import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.router import build_api_router
from app.contracts.identity import AuthContext


def client_for(repo):
    auth = AuthContext(
        tenant_id="tenant-a",
        user_id="alice",
        shop_ids={"shop-a"},
        permissions={"orchestrator:provision", "conversation:write", "history:read"},
    )

    async def authenticate(token):
        return auth

    async def ready():
        return True

    app = FastAPI()
    app.include_router(build_api_router(repo, authenticate, ready))
    return TestClient(app, headers={"Authorization": "Bearer fixture"}), auth.scope("shop-a")


def test_expected_revision_conflict_and_pinned_replay(repo, registry):
    client, scope = client_for(repo)
    registry.register(
        registry.get("shopops", "returns-v1").model_copy(update={"revision": "returns-v2"})
    )
    with client:
        o = client.post(
            "/api/v1/shops/shop-a/orchestrator",
            json={"template_id": "shopops", "config_revision": "returns-v1"},
        ).json()["orchestrator_id"]
        body = {
            "orchestrator_id": o,
            "client_conversation_id": "pinned",
            "expected_config_revision": "returns-v1",
        }
        first = client.post("/api/v1/shops/shop-a/conversations", json=body)
        assert first.status_code == 201
        asyncio.run(repo.activate_revision(scope, "shopops", "returns-v2"))
        replay = client.post("/api/v1/shops/shop-a/conversations", json=body)
        assert replay.status_code == 200 and replay.json() == first.json()
        mismatch = client.post(
            "/api/v1/shops/shop-a/conversations", json=body | {"client_conversation_id": "new"}
        )
        assert mismatch.status_code == 409
        assert mismatch.json()["error"]["code"] == "configuration_conflict"
        changed_replay = client.post(
            "/api/v1/shops/shop-a/conversations",
            json=body | {"expected_config_revision": "returns-v2"},
        )
        assert changed_replay.status_code == 409
        assert changed_replay.json()["error"]["code"] == "idempotency_conflict"
        new = client.post(
            "/api/v1/shops/shop-a/conversations",
            json=body | {"client_conversation_id": "new", "expected_config_revision": "returns-v2"},
        )
        assert new.status_code == 201
        assert (
            asyncio.run(repo.get_config_snapshot(scope, new.json()["conversation_id"])).revision
            == "returns-v2"
        )
        legacy = client.post(
            "/api/v1/shops/shop-a/conversations",
            json={"orchestrator_id": o, "client_conversation_id": "legacy"},
        )
        assert legacy.status_code == 201


def test_activation_immediately_before_create_transaction_is_rejected(repo, registry):
    client, scope = client_for(repo)
    registry.register(
        registry.get("shopops", "returns-v1").model_copy(update={"revision": "returns-v2"})
    )
    original = repo.create_conversation

    async def activate_then_create(*args, **kwargs):
        await repo.activate_revision(scope, "shopops", "returns-v2")
        return await original(*args, **kwargs)

    repo.create_conversation = activate_then_create
    with client:
        o = client.post(
            "/api/v1/shops/shop-a/orchestrator",
            json={"template_id": "shopops", "config_revision": "returns-v1"},
        ).json()["orchestrator_id"]
        result = client.post(
            "/api/v1/shops/shop-a/conversations",
            json={
                "orchestrator_id": o,
                "client_conversation_id": "race",
                "expected_config_revision": "returns-v1",
            },
        )
        assert result.status_code == 409
        assert result.json()["error"]["code"] == "configuration_conflict"
