import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.store import BusyError, CoreStore
from tests.test_agent_core_contract import M, handler
from tests.test_demo_phone_auth import config, login


@pytest.mark.parametrize("boundary", ["orchestrator", "conversations", "messages"])
def test_lost_receipt_exact_replay_restart(tmp_path, boundary):
    calls = []
    lost = False

    def transport(r):
        nonlocal lost
        calls.append(r)
        result = handler(r)
        if not lost and r.method == "POST" and r.url.path.endswith("/" + boundary):
            lost = True
            raise httpx.ReadTimeout("secret")
        return result

    settings = config(tmp_path)
    with TestClient(create_app(settings, httpx.MockTransport(transport))) as c:
        if boundary == "orchestrator":
            assert (
                c.post(
                    "/api/chat/auth/demo-phone", json={"phone_number": "+15550000001"}
                ).status_code
                == 503
            )
        headers = login(c)
        response = c.post(
            "/api/chat/messages",
            headers=headers,
            json={"text": "Hi", "client_message_id": "stable-key"},
        )
        if boundary != "orchestrator":
            assert "error" in response.text
    with TestClient(create_app(settings, httpx.MockTransport(transport))) as c:
        headers = login(c)
        history = c.get("/api/chat/messages", headers=headers)
        assert history.status_code == 200
        assert history.json()[-1]["id"] == M
        before = len([r for r in calls if r.url.path.endswith("/messages")])
        assert (
            "done"
            in c.post(
                "/api/chat/messages",
                headers=headers,
                json={"text": "Hi", "client_message_id": "stable-key"},
            ).text
        )
        assert len([r for r in calls if r.url.path.endswith("/messages")]) == before
    posts = [r for r in calls if r.method == "POST" and r.url.path.endswith("/" + boundary)]
    assert len(posts) == 2
    assert posts[0].content == posts[1].content


def test_pending_scope_cutover_and_lease_loss(tmp_path):
    store = CoreStore(str(tmp_path / "db"))
    store.initialize()
    store.space("a", "owner", "config")
    store.core_claim("a", "key", "payload", "worker")
    with pytest.raises(BusyError):
        store.core_claim("a", "other", "payload", "worker2")
    with pytest.raises(BusyError):
        store.core_claim("a", "key", "payload", "worker2")
    with pytest.raises(ValueError):
        store.core_claim("a", "key", "different", "worker2")
    with pytest.raises(BusyError):
        store.space("b", "owner", "other-config")
    with store.connect() as db:
        db.execute("UPDATE core_outbox SET lease=0")
    store.core_claim("a", "key", "payload", "worker2")
    with pytest.raises(BusyError):
        store.core_update("a", "key", "worker", run_id="wrong")
    store.core_update("a", "key", "worker2", status="completed")
    store.space("b", "owner", "other-config")


def test_legacy_migration_preserves_history_and_blocks_pending(tmp_path):
    from app.store import Store

    old = Store(str(tmp_path / "chat.db"))
    old.initialize()
    with old.connect() as db:
        db.execute("INSERT INTO messages(text,role) VALUES('legacy','assistant')")
        db.execute("UPDATE workspace SET session_id='sess_old'")
    core = CoreStore(old.path)
    core.initialize()
    assert old.history()[0]["text"] == "legacy"
    assert core.space("a", "owner", "config")["conversation"] is None
    old.claim("pending", "legacy-worker")
    with pytest.raises(BusyError):
        core.space("b", "owner", "config")


def test_rollback_to_legacy_refuses_pending_core_work(tmp_path):
    from app.settings import Settings

    store = CoreStore(str(tmp_path / "chat.db"))
    store.initialize()
    store.space("a", "owner", "configuration")
    store.core_claim("a", "key", "payload", "worker")
    with pytest.raises(RuntimeError, match="pending Core"):
        with TestClient(create_app(Settings("token", "key", "agent", store.path))):
            pass


def test_slow_completion_renews_lease_and_emits_heartbeat(tmp_path, monkeypatch):
    import asyncio

    from app.core_chat import CoreChat
    from tests.test_agent_core_contract import C, M, R

    async def exercise():
        chat = CoreChat(config(tmp_path))
        chat.heartbeat_interval = 0.002
        now = [1000.0]
        monkeypatch.setattr("app.store.time.time", lambda: now[0])
        chat.store.initialize()
        who = next(iter(chat.auth.identities.values()))
        space = chat.store.space(*chat.namespace(who))
        chat.store.core_space_update(space["namespace"], conversation=C)
        space["conversation"] = C
        row = chat.store.core_claim(
            space["namespace"], "stable-key", '{"content":"Hi","output_mode":"text"}', "worker"
        )
        chat.store.core_update(space["namespace"], "stable-key", "worker", run_id=R, message_id=M)
        row.update(run_id=R, message_id=M)

        async def slow_run(*args):
            for _ in range(3):
                await asyncio.sleep(0.1)
                now[0] += 15
            return {
                "run_id": R,
                "status": "completed",
                "response": {"kind": "answer", "text": "Hello", "sources": []},
            }

        async def pages(path, token):
            if "/artifacts" in path:
                return []
            return [
                {
                    "id": M,
                    "run_id": R,
                    "role": "assistant",
                    "content": "Hello",
                    "created_at": "2026-10-31T12:00:00Z",
                    "conversation_id": C,
                    "sequence": 2,
                }
            ]

        chat.run = slow_run
        chat.api.pages = pages
        events = [event async for event in chat.stream(who, space, row, "worker")]
        assert any(event.startswith(": heartbeat") for event in events)
        assert '"type":"done"' in events[-1]
        with chat.store.connect() as db:
            assert db.execute("SELECT status FROM core_outbox").fetchone()[0] == "completed"
        await chat.api.client.aclose()

    asyncio.run(exercise())
