import httpx
from fastapi.testclient import TestClient

from app.main import create_app
from tests.test_agent_core_contract import handler
from tests.test_demo_phone_auth import config, login


def test_new_page_login_starts_empty_but_original_page_keeps_context(tmp_path):
    with TestClient(create_app(config(tmp_path), httpx.MockTransport(handler))) as client:
        original = login(client)
        response = client.post(
            "/api/chat/messages",
            headers=original,
            json={"text": "Hi", "client_message_id": "stable-key"},
        )
        assert '"type":"done"' in response.text
        previous = client.get("/api/chat/messages", headers=original)
        assert previous.status_code == 200 and len(previous.json()) == 1

        reloaded = login(client)
        clean = client.get("/api/chat/messages", headers=reloaded)
        assert clean.status_code == 200
        assert clean.json() == []
        assert client.get("/api/chat/messages", headers=original).json() == previous.json()


def test_new_page_is_not_blocked_by_previous_page_pending_input(tmp_path):
    with TestClient(create_app(config(tmp_path), httpx.MockTransport(handler))) as client:
        original = login(client)
        chat = client.app.state.core_chat
        identity = chat.auth.resolve(original["Authorization"][7:])
        space = chat.store.space(*chat.namespace(identity))
        chat.store.core_claim(space["namespace"], "old-pending", "{}", "old-page")

        reloaded = login(client)
        clean = client.get("/api/chat/messages", headers=reloaded)
        assert clean.status_code == 200
        assert clean.json() == []
        with chat.store.connect() as db:
            pending = db.execute(
                "SELECT status,owner FROM core_outbox WHERE client_id='old-pending'"
            ).fetchone()
        assert tuple(pending) == ("pending", "old-page")
