import json
import sqlite3

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings
from tests.helpers import HEADERS, configured_app, events, stream, text, turn


def test_create_stream_root_only_authoritative_final_and_persistence(tmp_path):
    requests = []

    def handler(request):
        requests.append(request)
        assert request.url == "https://api.openai.com/v1/agents/sessions"
        assert request.headers["OpenAI-Beta"] == "agents=v1"
        assert request.headers["Authorization"] == "Bearer test-provider-key"
        assert json.loads(request.content) == {
            "agent_id": "agent_orchestrator",
            "environment": {"type": "none"},
            "input": "Hello",
            "stream": True,
        }
        return stream(
            {"type": "agent.session.created", "session": {"id": "sess_1"}},
            turn(),
            turn(turn_id="child", subagent_id="sub_1"),
            text("private", turn_id="child"),
            turn("completed", "child", "sub_1"),
            text("draft"),
            text("# Final\n\n| A | B |\n| - | - |\n| 1 | 2 |", "done"),
            turn("completed"),
        )

    app = configured_app(tmp_path, handler)
    with TestClient(app) as client:
        response = client.post("/api/chat/messages", headers=HEADERS, json={"text": "Hello"})
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        payloads = events(response)
        assert payloads[0] == {"type": "delta", "text": "draft"}
        assert [event["type"] for event in payloads] == ["delta", "done"]
        assert payloads[-1]["message"]["text"].startswith("# Final")
    with TestClient(configured_app(tmp_path, handler)) as client:
        history = client.get("/api/chat/messages", headers=HEADERS).json()
        assert [message["role"] for message in history] == ["user", "assistant"]
        assert history[-1] == payloads[-1]["message"]
        assert len(requests) == 1


def test_followup_opens_event_stream_before_idempotent_input(tmp_path):
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path))
        if request.url.path.endswith("/turns"):
            return httpx.Response(
                200,
                json={
                    "data": [{"id": "old", "subagent_id": None, "status": "completed"}],
                    "has_more": False,
                },
            )
        if request.method == "GET":
            assert request.url.params["stream"] == "true"
            return stream(turn(), text("Only final", "done"), turn("completed"))
        assert calls[-2] == ("GET", "/v1/agents/sessions/sess_1/events")
        assert request.headers["Idempotency-Key"]
        assert json.loads(request.content) == {
            "events": [
                {
                    "type": "agent.session.input.message",
                    "input": [
                        {"role": "user", "content": [{"type": "input_text", "text": "Next"}]}
                    ],
                }
            ]
        }
        return httpx.Response(200)

    app = configured_app(tmp_path, handler)
    with TestClient(app) as client:
        with sqlite3.connect(tmp_path / "chat.db") as db:
            db.execute("UPDATE workspace SET session_id='sess_1'")
        response = client.post("/api/chat/messages", headers=HEADERS, json={"text": "Next"})
        assert events(response)[-1]["message"]["text"] == "Only final"
    assert len(calls) == 3


@pytest.mark.parametrize("outcome", ["eof", "failed", "cancelled", "requires_action", "invalid"])
def test_unsuccessful_stream_never_persists_an_assistant(tmp_path, outcome):
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.path.endswith("/events"):
            assert json.loads(request.content) == {
                "events": [{"type": "agent.session.input.cancel"}]
            }
            return httpx.Response(200)
        tail = []
        if outcome in {"failed", "cancelled"}:
            tail = [turn(outcome)]
        if outcome == "requires_action":
            tail = [{"type": "agent.session.requires_action", "session": {"id": "sess_1"}}]
        if outcome == "invalid":
            return httpx.Response(200, content="data: invalid\n\n")
        return stream(
            {"type": "agent.session.created", "session": {"id": "sess_1"}},
            turn(),
            text("partial"),
            *tail,
        )

    with TestClient(configured_app(tmp_path, handler)) as client:
        response = client.post("/api/chat/messages", headers=HEADERS, json={"text": "Hello"})
        assert events(response)[-1]["type"] == "error"
        assert not any(event["type"] == "done" for event in events(response))
    with sqlite3.connect(tmp_path / "chat.db") as db:
        assert db.execute("SELECT role FROM messages").fetchall() == [("user",)]


def test_definite_rejection_does_not_lock_conversation_and_never_leaks_body(tmp_path):
    count = 0

    def handler(request):
        nonlocal count
        count += 1
        if count == 1:
            return httpx.Response(429, text="sensitive-upstream-value")
        return stream(
            {"type": "agent.session.created", "session": {"id": "sess_1"}},
            turn(),
            text("Ready", "done"),
            turn("completed"),
        )

    with TestClient(configured_app(tmp_path, handler)) as client:
        first = client.post("/api/chat/messages", headers=HEADERS, json={"text": "One"})
        assert events(first)[-1]["type"] == "error"
        assert "sensitive-upstream-value" not in first.text
        second = client.post("/api/chat/messages", headers=HEADERS, json={"text": "Two"})
        assert events(second)[-1]["type"] == "done"


def test_auth_validation_and_service_boundaries(tmp_path):
    def handler(_request):
        pytest.fail("Invalid or unauthorized input must not call the provider")

    with TestClient(configured_app(tmp_path, handler)) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/api/chat/messages").status_code == 401
        assert client.post("/api/chat/messages", json={"text": "x"}).status_code == 401
        assert client.get("/api/operations/incidents", headers=HEADERS).status_code == 404
        for value in ["", " \n\t ", "a" * 2001]:
            assert (
                client.post("/api/chat/messages", headers=HEADERS, json={"text": value}).status_code
                == 422
            )


@pytest.mark.parametrize("field", ["token", "api_key", "agent_id", "database"])
def test_missing_configuration_fails_startup(tmp_path, field):
    config = {
        "token": "test",
        "api_key": "test",
        "agent_id": "agent_test",
        "database": str(tmp_path / "db"),
    }
    config[field] = ""
    with pytest.raises(RuntimeError, match="is required"):
        with TestClient(create_app(Settings(**config), httpx.MockTransport(lambda _: None))):
            pass
