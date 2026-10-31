import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.mcp.data import build_data_app
from app.mcp.knowledge_memory import build_knowledge_memory_app
from app.tools.credentials import Credentials
from tests.mcp.support import KEY, OTHER_SHOP, OTHER_USER, SCOPE, HistoryStub

ROOT = Path(__file__).resolve().parents[2]
HEADERS = {"Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2025-06-18"}
DATES = {"sku": "SKU-A", "start_date": "2026-10-19", "end_date": "2026-10-25"}


def headers(
    audience: str,
    *,
    scope=SCOPE,
    conversation_id: str = "conv-a",
    revision: str = "returns-v1",
    permissions=("conversation:write", "conversation:write", "history:read"),
):
    token = Credentials(KEY).issue(scope, conversation_id, revision, audience, permissions)
    return HEADERS | {"Authorization": f"Bearer {token}"}


def call(client: TestClient, name: str, arguments: dict, auth: dict) -> dict:
    response = client.post(
        "/",
        json={
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
        headers=auth,
    )
    assert response.status_code == 200
    result = response.json()["result"]
    assert json.loads(result["content"][0]["text"]) == result["structuredContent"]
    return result["structuredContent"]


def test_data_metrics_reviews_empty_and_unknown() -> None:
    repo = HistoryStub()
    app = build_data_app(repository=repo, credentials=Credentials(KEY))
    with TestClient(app) as client:
        auth = headers("agent-core:data")
        data = call(client, "get_return_metrics", DATES, auth)
        assert data["data"]["orders"] == 100
        assert data["data"]["returns"] == 15
        assert data["data"]["return_rate"] == 15
        assert data["data"]["baseline"]["return_rate"] == 5
        assert data["data"]["change_percentage_points"] == 10
        reviews = call(client, "get_review_summary", DATES, auth)
        assert reviews["data"]["categories"][0]["category"] == "sizing"
        assert reviews["data"]["categories"][0]["evidence"]
        assert (
            call(client, "get_return_metrics", DATES | {"sku": "missing"}, auth)["error"]
            == "not_found"
        )
        empty = call(
            client,
            "get_return_metrics",
            DATES | {"start_date": "2020-01-01", "end_date": "2020-01-02"},
            auth,
        )
        assert empty["error"] is None
        assert empty["data"]["orders"] == 0
        assert empty["data"]["return_rate"] is None
        b = call(
            client,
            "get_return_metrics",
            DATES,
            headers("agent-core:data", scope=OTHER_SHOP, conversation_id="conv-b"),
        )
        assert b["data"]["return_rate"] == 1


def test_invalid_credential_rejected_before_repository_access() -> None:
    repo = HistoryStub()
    with TestClient(build_data_app(repository=repo, credentials=Credentials(KEY))) as client:
        for auth in (
            {},
            HEADERS | {"Authorization": "Bearer bad"},
            headers("agent-core:knowledge-memory"),
        ):
            response = client.post("/", json={"method": "tools/list"}, headers=auth)
            assert response.status_code == 401
        assert repo.calls == 0
        response = client.post(
            "/",
            json={},
            headers=headers("agent-core:data") | {"Origin": "https://attacker.example"},
        )
        assert response.status_code == 403
        assert repo.calls == 0


@pytest.mark.parametrize("scope,cid", [(OTHER_SHOP, "conv-a"), (OTHER_USER, "conv-a")])
def test_signed_wrong_owner_scope_never_reads_data(scope, cid) -> None:
    repo = HistoryStub()
    with TestClient(build_data_app(repository=repo, credentials=Credentials(KEY))) as client:
        result = call(
            client,
            "get_return_metrics",
            DATES,
            headers("agent-core:data", scope=scope, conversation_id=cid),
        )
        assert result["error"] == "permission_denied"


def test_capabilities_permissions_and_pinned_revision() -> None:
    repo = HistoryStub()
    with TestClient(build_data_app(repository=repo, credentials=Credentials(KEY))) as client:
        assert (
            call(client, "get_return_metrics", DATES, headers("agent-core:data", permissions=()))[
                "error"
            ]
            == "permission_denied"
        )
        assert (
            call(
                client,
                "get_return_metrics",
                DATES,
                headers("agent-core:data", revision="new-revision"),
            )["error"]
            == "permission_denied"
        )
        assert (
            call(
                client,
                "get_return_metrics",
                DATES | {"shop_id": "shop-b"},
                headers("agent-core:data"),
            )["error"]
            == "invalid_input"
        )


def test_knowledge_version_history_boundary_and_integrity(tmp_path: Path) -> None:
    repo = HistoryStub()
    app = build_knowledge_memory_app(repository=repo, credentials=Credentials(KEY))
    with TestClient(app) as client:
        auth = headers("agent-core:knowledge-memory")
        result = call(client, "search_knowledge", {"query": "sizing", "limit": 1}, auth)
        assert result["data"]["matches"][0]["bundle_id"] == "returns-v1"
        assert result["data"]["matches"][0]["version"] == "1"
        history = call(client, "get_conversation_history", {"before_sequence": 7, "limit": 2}, auth)
        assert [m["sequence"] for m in history["data"]["messages"]] == [5, 6]
        assert all(m["conversation_id"] == "conv-a" for m in history["data"]["messages"])
        assert (
            call(
                client,
                "get_conversation_history",
                {"limit": 1},
                headers("agent-core:knowledge-memory", permissions=("conversation:write",)),
            )["error"]
            == "permission_denied"
        )
    import shutil

    bundle = tmp_path / "returns-v1"
    shutil.copytree(ROOT / "knowledge/returns-v1", bundle)
    (bundle / "sizing.md").write_text("tampered")
    with pytest.raises(ValueError):
        build_knowledge_memory_app(
            repository=repo, credentials=Credentials(KEY), bundle_path=bundle
        )


def test_remote_mode_disables_mock_data() -> None:
    assert (
        build_data_app(repository=HistoryStub(), credentials=Credentials(KEY), mode="remote")
        is None
    )
    with pytest.raises(ValueError):
        build_data_app(repository=HistoryStub(), credentials=Credentials(KEY), mode="invalid")


def test_history_large_payload_rejected_without_truncation() -> None:
    repo = HistoryStub()
    repo.messages["conv-a"] = [
        m.model_copy(update={"content": "é" * 10000}) for m in repo.messages["conv-a"]
    ]
    with TestClient(
        build_knowledge_memory_app(repository=repo, credentials=Credentials(KEY))
    ) as client:
        result = call(
            client,
            "get_conversation_history",
            {"limit": 20},
            headers("agent-core:knowledge-memory"),
        )
        assert result["error"] == "upstream_unavailable"
        assert result["data"] is None


def test_initialize_notifications_list_and_get() -> None:
    with TestClient(
        build_data_app(repository=HistoryStub(), credentials=Credentials(KEY))
    ) as client:
        auth = headers("agent-core:data")
        result = client.post(
            "/",
            headers=auth,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1"},
                },
            },
        )
        assert result.json()["result"]["capabilities"] == {"tools": {"listChanged": False}}
        response = client.post(
            "/", headers=auth, json={"jsonrpc": "2.0", "method": "notifications/initialized"}
        )
        assert response.status_code == 202 and not response.content
        response = client.post(
            "/", headers=auth, json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
        )
        assert {x["name"] for x in response.json()["result"]["tools"]} == {
            "get_return_metrics",
            "get_review_summary",
        }
        assert client.get("/", headers=auth).status_code == 405


def test_history_pages_beyond_first_repository_page() -> None:
    repo = HistoryStub()
    original = repo.messages["conv-a"][0]
    repo.messages["conv-a"] = [
        original.model_copy(update={"id": f"message-{i}", "sequence": i}) for i in range(1, 151)
    ]
    with TestClient(
        build_knowledge_memory_app(repository=repo, credentials=Credentials(KEY))
    ) as client:
        result = call(
            client,
            "get_conversation_history",
            {"before_sequence": 125, "limit": 3},
            headers("agent-core:knowledge-memory"),
        )
        assert result["error"] is None
        assert [m["sequence"] for m in result["data"]["messages"]] == [122, 123, 124]
