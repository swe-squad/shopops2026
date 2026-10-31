import time

from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.contracts.models import Source
from app.contracts.tools import ToolDefinition, ToolResult
from app.main import create_app
from app.providers.fake import FakeProvider, Scenario
from tests.integration.test_runtime import environment


class FixtureBridge:
    """Test-only tool substitute while T04 is absent; not MCP acceptance evidence."""

    def __init__(self):
        self.scopes = []

    def definitions(self, config):
        return (
            ToolDefinition(
                name="get_return_metrics", description="Synthetic test", input_schema={}
            ),
        )

    async def execute(self, scope, conversation_id, config, call):
        self.scopes.append(scope)
        return ToolResult(
            data={"returns": 15, "orders": 100},
            sources=(Source(type="data", reference="fixture:integration"),),
        )


def start_conversation(client):
    response = client.post(
        "/api/v1/shops/shop-a/orchestrator",
        json={"template_id": "shopops", "config_revision": "returns-v1"},
    )
    assert response.status_code == 201, response.text
    response = client.post(
        "/api/v1/shops/shop-a/conversations",
        json={
            "orchestrator_id": response.json()["orchestrator_id"],
            "client_conversation_id": "integration",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["conversation_id"]


def completed(client, run_id):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/runs/{run_id}")
        assert response.status_code == 200, response.text
        if response.json()["status"] in {"completed", "failed", "cancelled"}:
            assert response.json()["status"] == "completed", response.text
            return response.json()
        time.sleep(0.01)
    raise AssertionError("Worker did not complete the persisted run")


def test_api_storage_worker_and_fake_provider_share_context(tmp_path):
    settings = Settings.from_env(environment(tmp_path))
    provider = FakeProvider([Scenario(tool_name="get_return_metrics"), Scenario()])
    bridge = FixtureBridge()
    app = create_app(settings=settings, provider=provider, bridge=bridge)
    with TestClient(app, headers={"Authorization": "Bearer local-alice"}) as client:
        conversation_id = start_conversation(client)
        path = f"/api/v1/conversations/{conversation_id}/messages"
        body = {"client_message_id": "first", "content": "SKU-A returns"}
        submitted = client.post(path, json=body)
        assert submitted.status_code == 202, submitted.text
        run_id = submitted.json()["run_id"]
        result = completed(client, run_id)
        assert result["response"]["sources"] == [
            {"type": "data", "reference": "fixture:integration"}
        ]
        assert "conversation:write" in bridge.scopes[0].permissions
        assert bridge.scopes[0].user_id == "alice"
        assert client.post(path, json=body).json() == submitted.json()
        conflict = client.post(path, json=body | {"content": "changed"})
        assert conflict.status_code == 409
        followup = client.post(path, json={"client_message_id": "second", "content": "more?"})
        assert followup.status_code == 202
        completed(client, followup.json()["run_id"])
        assert len(provider.sessions) == 1
        assert next(iter(provider.sessions.values())).turn_count == 2
        history_path = f"/api/v1/conversations/{conversation_id}/history"
        assert len(client.get(history_path).json()["items"]) == 4
        assert (
            client.get(history_path, headers={"Authorization": "Bearer local-bob"}).status_code
            == 404
        )
        assert (
            client.get(
                f"/api/v1/runs/{run_id}", headers={"Authorization": "Bearer local-carol"}
            ).status_code
            == 404
        )
        assert client.get("/api/v1/health").status_code == 200
        # Actual MCP applications are not yet mounted; readiness must remain honest.
        assert client.get("/api/v1/ready").status_code == 503
    # Reload SQLite through a new app, then prove history and idempotent receipt survive.
    with TestClient(
        create_app(settings=settings), headers={"Authorization": "Bearer local-alice"}
    ) as client:
        assert len(client.get(history_path).json()["items"]) == 4
        assert client.post(path, json=body).json() == submitted.json()


def test_missing_permission_on_owned_sqlite_conversation_is_403(tmp_path):
    from app.api.router import build_api_router
    from app.contracts.identity import AuthContext

    settings = Settings.from_env(environment(tmp_path))
    with TestClient(
        create_app(settings=settings), headers={"Authorization": "Bearer local-alice"}
    ) as client:
        conversation_id = start_conversation(client)

    async def denied_auth(token):
        return AuthContext(
            tenant_id="tenant-a",
            user_id="alice",
            shop_ids=frozenset({"shop-a"}),
            permissions=frozenset(),
        )

    def router_factory(repo, config, readiness):
        return build_api_router(repo, denied_auth, readiness)

    with TestClient(
        create_app(settings=settings, router_factory=router_factory),
        headers={"Authorization": "Bearer synthetic-denied"},
    ) as client:
        response = client.get(f"/api/v1/conversations/{conversation_id}/history")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"
