import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.contracts.errors import NotFound
from app.contracts.identity import AuthContext


class EmptyRepository:
    async def get_conversation(self, scope, conversation_id):
        raise NotFound()

    async def get_run(self, scope, run_id):
        raise NotFound()


async def authenticate(token):
    return AuthContext(
        tenant_id="tenant-a",
        user_id="alice",
        shop_ids={"shop-a"},
        permissions={"conversation:write", "history:read"},
    )


async def ready():
    return False


@pytest.fixture
def client():
    from app.api.router import build_api_router

    app = FastAPI()
    app.include_router(build_api_router(EmptyRepository(), authenticate, ready))
    return TestClient(app)


def test_health_and_readiness(client):
    assert client.get("/api/v1/health").json() == {"status": "ok"}
    assert client.get("/api/v1/ready").status_code == 503


@pytest.mark.parametrize("header", [None, "Basic secret", "Bearer", "Bearer a b"])
def test_bearer_required(client, header):
    response = client.get(
        "/api/v1/runs/run", headers={} if header is None else {"Authorization": header}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
    assert "request_id" in response.json()


@pytest.mark.parametrize(
    "body",
    [
        {"client_message_id": "x", "content": "  "},
        {"client_message_id": "x" * 129, "content": "hello"},
        {"client_message_id": "x", "content": "x" * 8001},
        {"client_message_id": "x", "content": "hello", "tenant_id": "foreign"},
    ],
)
def test_invalid_messages(client, body):
    response = client.post(
        "/api/v1/conversations/c/messages", json=body, headers={"Authorization": "Bearer local"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_input"


def test_body_limit(client):
    response = client.post(
        "/api/v1/conversations/c/messages",
        content=b" " * 65537,
        headers={"Authorization": "Bearer local"},
    )
    assert response.status_code == 413


def test_out_of_scope_is_404(client):
    response = client.get("/api/v1/runs/foreign", headers={"Authorization": "Bearer local"})
    assert response.status_code == 404
