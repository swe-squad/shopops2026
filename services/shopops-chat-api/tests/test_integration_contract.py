import sqlite3

import httpx
import pytest
from fastapi.testclient import TestClient

from tests.helpers import HEADERS, configured_app, events
from tests.test_recovery import seed_pending


def test_openapi_declares_stream_events_bearer_and_json_errors(tmp_path):
    def handler(_request):
        pytest.fail("Contract inspection must not call the provider")

    with TestClient(configured_app(tmp_path, handler)) as client:
        schema = client.get("/openapi.json").json()
    assert schema["components"]["securitySchemes"]["WorkspaceToken"]["scheme"] == "bearer"
    assert "security" not in schema["paths"]["/health"]["get"]
    post = schema["paths"]["/api/chat/messages"]["post"]
    assert post["security"] == [{"WorkspaceToken": []}]
    assert set(post["responses"]["200"]["content"]) == {"text/event-stream"}
    for code in ["401", "409", "422", "502"]:
        assert set(post["responses"][code]["content"]) == {"application/json"}
    stream_schema = post["responses"]["200"]["content"]["text/event-stream"]["schema"]
    for item in stream_schema["oneOf"]:
        assert item["$ref"].split("/")[-1] in schema["components"]["schemas"]
    assert {"DeltaEvent", "DoneEvent", "ErrorEvent"} <= set(schema["components"]["schemas"])


@pytest.mark.parametrize(
    "malformed",
    [
        "json",
        "session",
        "turn",
        "turn-list",
        "page",
        "page-item",
        "has-more",
        "cursor",
        "content",
        "part",
        "text",
    ],
)
def test_malformed_recovery_preserves_history_and_returns_sanitized_502(tmp_path, malformed):
    store = seed_pending(tmp_path, provider_turn=None if malformed == "turn-list" else "turn_1")
    calls = []

    def handler(request):
        calls.append(request)
        assert request.method == "GET"
        if malformed == "json":
            return httpx.Response(200, text="private-upstream-value")
        if request.url.path.endswith("/sess_1"):
            return httpx.Response(200, json={"status": [] if malformed == "session" else "idle"})
        if request.url.path.endswith("/turns"):
            return httpx.Response(200, json={"data": [{"subagent_id": None}], "has_more": False})
        if request.url.path.endswith("/turn_1"):
            payload = {"subagent_id": None}
            if malformed != "turn":
                payload["status"] = "completed"
            return httpx.Response(200, json=payload)
        content = [{"type": "output_text", "text": None if malformed == "text" else "Answer"}]
        if malformed == "content":
            content = None
        if malformed == "part":
            content = [None]
        data = [{"type": "message", "role": "assistant", "status": "completed", "content": content}]
        if malformed == "page":
            data = "private-upstream-value"
        if malformed == "page-item":
            data = [None]
        has_more = "private-upstream-value" if malformed == "has-more" else malformed == "cursor"
        return httpx.Response(200, json={"data": data, "has_more": has_more, "last_id": []})

    with TestClient(configured_app(tmp_path, handler), raise_server_exceptions=False) as client:
        history = client.get("/api/chat/messages", headers=HEADERS)
        assert history.status_code == 200
        assert [message["text"] for message in history.json()] == ["Original"]
        response = client.post("/api/chat/messages", headers=HEADERS, json={"text": "Next"})
        assert response.status_code == 502
        assert "private-upstream-value" not in response.text
        assert set(response.json()) == {"detail"}
    with store.connect() as db:
        row = db.execute("SELECT status,owner FROM turns").fetchone()
        assert tuple(row) == ("pending", None)
        assert db.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 1


def test_existing_active_provider_turn_is_not_cancelled_by_rejected_submission(tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        if request.method == "POST":
            return httpx.Response(200)
        return httpx.Response(
            200,
            json={
                "data": [{"id": "already-running", "subagent_id": None, "status": "in_progress"}],
                "has_more": False,
            },
        )

    with TestClient(configured_app(tmp_path, handler)) as client:
        with sqlite3.connect(tmp_path / "chat.db") as db:
            db.execute("UPDATE workspace SET session_id='sess_1'")
        response = client.post("/api/chat/messages", headers=HEADERS, json={"text": "Next"})
        assert events(response)[-1]["type"] == "error"
    assert [(request.method, request.url.path) for request in calls] == [
        ("GET", "/v1/agents/sessions/sess_1/turns")
    ]
    with sqlite3.connect(tmp_path / "chat.db") as db:
        assert db.execute("SELECT dispatched,owner FROM turns").fetchone() == (0, None)


@pytest.mark.parametrize("authorization", ["", "Basic test-token", "Bearer wrong", "Bearer"])
def test_invalid_bearer_tokens_never_reach_chat_provider(tmp_path, authorization):
    def handler(_request):
        pytest.fail("Unauthorized input must not reach the provider")

    with TestClient(configured_app(tmp_path, handler)) as client:
        headers = {"Authorization": authorization}
        assert client.get("/api/chat/messages", headers=headers).status_code == 401
        response = client.post("/api/chat/messages", headers=headers, json={"text": "Rejected"})
        assert response.status_code == 401
        assert client.get("/api/chat/messages", headers=HEADERS).json() == []
