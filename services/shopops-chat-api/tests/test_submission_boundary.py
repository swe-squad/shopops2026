import json
import sqlite3

import httpx
import pytest
from fastapi.testclient import TestClient

from tests.helpers import HEADERS, configured_app, events, stream, text, turn


def saved_turns():
    return httpx.Response(
        200,
        json={
            "data": [{"id": "old", "subagent_id": None, "status": "completed"}],
            "has_more": False,
        },
    )


def action(request):
    if request.method == "GET":
        return "read"
    if request.url.path.endswith("/sessions"):
        return "create"
    return json.loads(request.content)["events"][0]["type"]


def pending_state(tmp_path):
    with sqlite3.connect(tmp_path / "chat.db") as db:
        return db.execute(
            "SELECT dispatched,status,owner FROM turns ORDER BY rowid DESC"
        ).fetchone()


@pytest.mark.parametrize("failure", ["http-error", "timeout", "rejected"])
def test_event_stream_open_failure_is_undispatched_and_retryable(tmp_path, failure):
    calls = []
    opens = 0

    def handler(request):
        nonlocal opens
        calls.append(request)
        if request.url.path.endswith("/turns"):
            return saved_turns()
        if request.method == "GET":
            opens += 1
            if opens == 1:
                if failure == "timeout":
                    raise httpx.ReadTimeout("private-upstream-value", request=request)
                return httpx.Response(401 if failure == "rejected" else 503)
            return stream(turn(), text("Retry succeeded", "done"), turn("completed"))
        return httpx.Response(200)

    with TestClient(configured_app(tmp_path, handler)) as client:
        with sqlite3.connect(tmp_path / "chat.db") as db:
            db.execute("UPDATE workspace SET session_id='sess_1'")
        first = client.post("/api/chat/messages", headers=HEADERS, json={"text": "First"})
        assert events(first)[-1]["type"] == "error"
        assert "private-upstream-value" not in first.text
        assert [action(request) for request in calls] == ["read", "read"]
        assert pending_state(tmp_path)[0] == 0
        count = len(calls)
        history = client.get("/api/chat/messages", headers=HEADERS)
        assert [message["text"] for message in history.json()] == ["First"]
        assert len(calls) == count
        assert pending_state(tmp_path) == (0, "failed", None)
        retry = client.post("/api/chat/messages", headers=HEADERS, json={"text": "Retry"})
        assert events(retry)[-1]["type"] == "done"
    assert [action(request) for request in calls].count("agent.session.input.message") == 1
    assert "agent.session.input.cancel" not in [action(request) for request in calls]


@pytest.mark.parametrize("session", [None, "sess_1"])
@pytest.mark.parametrize("failure", ["rejected", "timeout", "server-error", "redirect"])
def test_input_attempt_is_durable_but_only_acceptance_allows_cancellation(
    tmp_path, session, failure
):
    calls = []
    inputs = 0

    def handler(request):
        nonlocal inputs
        calls.append(request)
        kind = action(request)
        if request.url.path.endswith("/turns"):
            return saved_turns()
        if request.url.path.endswith("/sess_1"):
            return httpx.Response(200, json={"status": "idle"})
        if kind == "read":
            return stream(turn(), text("Accepted", "done"), turn("completed"))
        if kind == "agent.session.input.cancel":
            return httpx.Response(200)
        inputs += 1
        # Record uncertain-send intent before any input-bearing HTTP request can leave the process.
        dispatched, status, owner = pending_state(tmp_path)
        assert dispatched == 1 and status == "pending" and owner is not None
        if inputs == 1:
            if failure == "timeout":
                raise httpx.ReadTimeout("private-upstream-value", request=request)
            status = {"rejected": 429, "server-error": 503, "redirect": 307}[failure]
            return httpx.Response(status, text="private-upstream-value")
        if kind == "create":
            return stream(
                {"type": "agent.session.created", "session": {"id": "sess_1"}},
                turn(),
                text("Accepted", "done"),
                turn("completed"),
            )
        return httpx.Response(200)

    with TestClient(configured_app(tmp_path, handler)) as client:
        if session:
            with sqlite3.connect(tmp_path / "chat.db") as db:
                db.execute("UPDATE workspace SET session_id=?", (session,))
        first = client.post("/api/chat/messages", headers=HEADERS, json={"text": "First"})
        assert events(first)[-1]["type"] == "error"
        assert "private-upstream-value" not in first.text
        expected_status = "failed" if failure == "rejected" else "pending"
        assert pending_state(tmp_path) == (1, expected_status, None)
        next_response = client.post("/api/chat/messages", headers=HEADERS, json={"text": "Next"})
        if failure == "rejected":
            assert events(next_response)[-1]["type"] == "done"
            assert inputs == 2
        else:
            assert next_response.status_code == 409
            assert inputs == 1
            with sqlite3.connect(tmp_path / "chat.db") as db:
                assert db.execute("SELECT text FROM messages").fetchall() == [("First",)]
    assert "agent.session.input.cancel" not in [action(request) for request in calls]


def test_accepted_followup_interruption_cancels_only_after_input_acceptance(tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.path.endswith("/turns"):
            return saved_turns()
        if request.method == "GET":
            return stream(turn(), text("Partial"))
        return httpx.Response(200)

    with TestClient(configured_app(tmp_path, handler)) as client:
        with sqlite3.connect(tmp_path / "chat.db") as db:
            db.execute("UPDATE workspace SET session_id='sess_1'")
        response = client.post("/api/chat/messages", headers=HEADERS, json={"text": "First"})
        assert [event["type"] for event in events(response)] == ["delta", "error"]
    assert [action(request) for request in calls] == [
        "read",
        "read",
        "agent.session.input.message",
        "agent.session.input.cancel",
    ]
    assert pending_state(tmp_path) == (1, "pending", None)
