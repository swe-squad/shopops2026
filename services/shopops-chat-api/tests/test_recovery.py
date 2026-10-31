import asyncio
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from fastapi.testclient import TestClient

from app.chat import Chat
from app.provider import AgentsProvider
from app.store import BusyError, Store
from tests.helpers import HEADERS, configured_app, stream, text, turn


def seed_pending(tmp_path, session="sess_1", provider_turn="turn_1", dispatched=1):
    store = Store(str(tmp_path / "chat.db"))
    store.initialize()
    pending = store.claim("Original", "old-owner")
    values = {"dispatched": dispatched}
    if session:
        values["session_id"] = session
    if provider_turn:
        values["provider_turn_id"] = provider_turn
    store.update(pending["submission_key"], "old-owner", **values)
    store.release(pending["submission_key"], "old-owner")
    return store


def test_restart_recovers_completed_reply_with_paginated_items_without_resending(tmp_path):
    seed_pending(tmp_path)
    calls = []

    def handler(request):
        calls.append(request)
        assert request.method == "GET"
        if request.url.path.endswith("/sess_1"):
            return httpx.Response(200, json={"id": "sess_1", "status": "idle"})
        if request.url.path.endswith("/turn_1"):
            return httpx.Response(
                200, json={"id": "turn_1", "status": "completed", "subagent_id": None}
            )
        assert request.url.path.endswith("/turn_1/items")
        if "after" not in request.url.params:
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "user",
                            "type": "message",
                            "role": "user",
                            "status": "completed",
                            "content": [],
                        }
                    ],
                    "has_more": True,
                    "last_id": "user",
                },
            )
        assert request.url.params["after"] == "user"
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "assistant",
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": [{"type": "output_text", "text": "Recovered answer"}],
                    }
                ],
                "has_more": False,
            },
        )

    with TestClient(configured_app(tmp_path, handler)) as client:
        response = client.get("/api/chat/messages", headers=HEADERS)
        assert response.json()[-1]["text"] == "Recovered answer"
        assert len(response.json()) == 2
        assert client.get("/api/chat/messages", headers=HEADERS).json() == response.json()
    assert len(calls) == 4


@pytest.mark.parametrize("session", [None, "sess_1"])
def test_uncertain_or_active_turn_blocks_new_input_without_duplicates(tmp_path, session):
    seed_pending(tmp_path, session=session)
    calls = []

    def handler(request):
        calls.append(request)
        assert request.method == "GET"
        if request.url.path.endswith("/sess_1"):
            return httpx.Response(200, json={"status": "in_progress"})
        return httpx.Response(
            200, json={"id": "turn_1", "status": "in_progress", "subagent_id": None}
        )

    with TestClient(configured_app(tmp_path, handler)) as client:
        response = client.post("/api/chat/messages", headers=HEADERS, json={"text": "Again"})
        assert response.status_code == 409
    with sqlite3.connect(tmp_path / "chat.db") as db:
        assert db.execute("SELECT text FROM messages").fetchall() == [("Original",)]
    assert len(calls) == (2 if session else 0)


def test_recovery_finds_only_turn_after_saved_baseline(tmp_path):
    store = seed_pending(tmp_path, provider_turn=None)
    with store.connect() as db:
        db.execute("UPDATE turns SET baseline_turn_id='old'")

    def handler(request):
        assert request.method == "GET"
        if request.url.path.endswith("/sess_1"):
            return httpx.Response(200, json={"status": "idle"})
        if request.url.path.endswith("/turns"):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"id": "old", "subagent_id": None},
                        {"id": "child", "subagent_id": "sub"},
                        {"id": "new", "subagent_id": None},
                    ],
                    "has_more": False,
                },
            )
        assert request.url.path.endswith("/turns/new")
        return httpx.Response(200, json={"id": "new", "subagent_id": None, "status": "cancelled"})

    with TestClient(configured_app(tmp_path, handler)) as client:
        assert len(client.get("/api/chat/messages", headers=HEADERS).json()) == 1
    with store.connect() as db:
        assert db.execute("SELECT status FROM turns").fetchone()[0] == "failed"


def test_crash_before_dispatch_is_released_without_network(tmp_path):
    seed_pending(tmp_path, session=None, provider_turn=None, dispatched=0)

    def handler(_request):
        pytest.fail("Undispatched work has no provider state to recover")

    with TestClient(configured_app(tmp_path, handler)) as client:
        assert len(client.get("/api/chat/messages", headers=HEADERS).json()) == 1
    with sqlite3.connect(tmp_path / "chat.db") as db:
        assert db.execute("SELECT status FROM turns").fetchone()[0] == "failed"


def test_persistent_lease_serializes_workers_and_rejects_old_owner(tmp_path):
    store = Store(str(tmp_path / "chat.db"))
    store.initialize()

    def claim(owner):
        try:
            return Store(store.path).claim("Hello", owner)
        except BusyError:
            return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(claim, ["one", "two"]))
    accepted = [value for value in results if value]
    assert len(accepted) == 1
    old = accepted[0]
    with store.connect() as db:
        db.execute("UPDATE turns SET lease_until=0")
    reclaimed = store.claim(None, "new")
    assert reclaimed["recover"] is True
    with pytest.raises(BusyError):
        store.finish(old["submission_key"], old["owner"], "Stale answer")
    store.finish(old["submission_key"], "new", "Answer")
    assert [item["text"] for item in store.history()] == ["Hello", "Answer"]


def test_consumer_disconnect_cancels_upstream_and_retains_recoverable_turn(tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.path.endswith("/events"):
            assert json.loads(request.content) == {
                "events": [{"type": "agent.session.input.cancel"}]
            }
            return httpx.Response(200)
        return stream(
            {"type": "agent.session.created", "session": {"id": "sess_1"}}, turn(), text("Partial")
        )

    async def run():
        store = Store(str(tmp_path / "chat.db"))
        store.initialize()
        provider = AgentsProvider("test", "agent_test", httpx.MockTransport(handler))
        chat = Chat(store, provider)
        pending, owner = await chat.prepare("Hi")
        output = chat.stream(pending, owner, "Hi")
        assert "Partial" in await anext(output)
        # Session persistence precedes the first text sent to the client.
        with store.connect() as db:
            assert db.execute("SELECT session_id FROM workspace").fetchone()[0] == "sess_1"
        await output.aclose()
        await provider.close()
        with store.connect() as db:
            saved = dict(db.execute("SELECT * FROM turns").fetchone())
            assert saved["status"] == "pending" and saved["owner"] is None
            assert saved["provider_turn_id"] == "turn_1"
        assert [item["role"] for item in store.history()] == ["user"]

    asyncio.run(run())
    assert len(calls) == 2
