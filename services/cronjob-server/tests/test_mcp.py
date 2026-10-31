import json
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.main import create_app
from app.pipeline.publish import publish
from app.storage.db import connect
from app.storage.migrations import migrate
from tests.test_normalization import full_snapshot
from tests.test_reads import Grants

HEADERS = {"Authorization": "Bearer integration-test-token"}


def payload() -> dict:
    now = datetime.now(UTC)
    return {
        "subject": "agent-a",
        "shop_key": "lazada:1001",
        "resource": "snapshot",
        "start": (now - timedelta(days=2)).isoformat(),
        "end": (now - timedelta(days=1)).isoformat(),
        "idempotency_key": "request-a",
    }


def setup(database, monkeypatch):
    migrate()
    publish(full_snapshot())
    monkeypatch.setenv("MCP_SERVICE_TOKEN", "integration-test-token")
    monkeypatch.setenv(
        "MCP_SUBJECT_USERS_JSON", json.dumps({"agent-a": "+84900000001", "agent-b": "+84900000001"})
    )
    source = Grants()
    return source, create_app(source=source, start_worker=False)


def test_mcp_auth_scope_and_fail_closed_configuration(database, monkeypatch):
    source, app = setup(database, monkeypatch)
    with TestClient(app) as client:
        body = payload()
        assert client.post("/v1/refreshes", json=body).status_code == 401
        assert (
            client.post(
                "/v1/refreshes", json=body, headers={"X-Demo-User-Id": "+84900000001"}
            ).status_code
            == 401
        )
        assert (
            client.post(
                "/v1/refreshes", json=body | {"subject": "unknown"}, headers=HEADERS
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/v1/refreshes", json=body | {"shop_key": "shopify:1001"}, headers=HEADERS
            ).status_code
            == 404
        )
        assert (
            client.post(
                "/v1/refreshes", json=body | {"resource": "orders"}, headers=HEADERS
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/v1/refreshes", json=body | {"start": body["end"]}, headers=HEADERS
            ).status_code
            == 422
        )
        monkeypatch.delenv("MCP_SERVICE_TOKEN")
        assert client.post("/v1/refreshes", json=body, headers=HEADERS).status_code == 401
        with connect() as conn:
            assert conn.execute("SELECT count(*) n FROM sync.runs").fetchone()["n"] == 0


def test_mcp_replay_ownership_and_snapshot_completion(database, monkeypatch):
    source, app = setup(database, monkeypatch)
    with TestClient(app) as client:
        body = payload()
        first = client.post("/v1/refreshes", json=body, headers=HEADERS)
        assert first.status_code == 202, first.text
        operation = first.json()["operation_id"]
        repeated = client.post("/v1/refreshes", json=body, headers=HEADERS)
        assert repeated.json() == first.json()
        assert (
            client.post(
                "/v1/refreshes", json=body | {"end": datetime.now(UTC).isoformat()}, headers=HEADERS
            ).status_code
            == 409
        )
        assert (
            client.post(
                "/v1/refreshes", json=body | {"idempotency_key": "other"}, headers=HEADERS
            ).status_code
            == 429
        )
        path = f"/v1/operations/{operation}"
        params = {"subject": body["subject"], "shop_key": body["shop_key"]}
        assert (
            client.get(path, params=params | {"subject": "agent-b"}, headers=HEADERS).status_code
            == 404
        )
        assert client.get(path, params=params, headers=HEADERS).json()["status"] == "queued"
        # Publication marks the run succeeded in the SAME transaction as the new data.
        publish(full_snapshot(), operation)
        response = client.get(path, params=params, headers=HEADERS)
        assert response.json() == {
            "operation_id": operation,
            "subject": "agent-a",
            "shop_key": "lazada:1001",
            "status": "snapshot_ready",
            "coverage": None,
            "refresh_mode": "full_snapshot",
            "applied_source_revision": 1,
            "error_code": None,
        }
        source.allowed = False
        assert client.get(path, params=params, headers=HEADERS).status_code == 403
        assert client.post("/v1/refreshes", json=body, headers=HEADERS).status_code == 403
