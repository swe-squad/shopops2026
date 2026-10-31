import json
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.test_demo_phone_auth import config, login

C, ORCHESTRATOR, R, M = [str(uuid.uuid4()) for _ in range(4)]


def handler(request):
    assert request.headers["Authorization"] == "Bearer local-alice"
    assert request.url.host == "core"
    body = json.loads(request.content) if request.content else None
    path = request.url.path
    if path.endswith("/orchestrator"):
        assert body == {"template_id": "shopops", "config_revision": "v1"}
        return httpx.Response(201, json={"orchestrator_id": ORCHESTRATOR, "config_revision": "v1"})
    if path.endswith("/conversations"):
        assert body["orchestrator_id"] == ORCHESTRATOR
        return httpx.Response(201, json={"conversation_id": C})
    if path.endswith("/messages"):
        assert body["client_message_id"] == "stable-key"
        return httpx.Response(
            202, json={"message_id": M, "run_id": R, "polling_url": "https://evil/"}
        )
    if path.endswith("/history"):
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": M,
                        "conversation_id": C,
                        "run_id": R,
                        "role": "assistant",
                        "content": "Xin chào",
                        "sequence": 2,
                        "created_at": "2026-10-31T12:00:00Z",
                    }
                ],
                "next_cursor": None,
            },
        )
    if path.endswith("/artifacts"):
        return httpx.Response(200, json={"items": [], "next_cursor": None})
    assert path == "/api/v1/runs/" + R
    return httpx.Response(
        200,
        json={
            "run_id": R,
            "status": "completed",
            "response": {"kind": "clarification", "text": "Xin chào", "sources": []},
            "error": None,
        },
    )


def test_core_receipt_history_sse_replay_and_conflict(tmp_path):
    calls = []

    def transport(r):
        calls.append(r)
        return handler(r)

    with TestClient(create_app(config(tmp_path), httpx.MockTransport(transport))) as c:
        headers = login(c)
        response = c.post(
            "/api/chat/messages",
            headers=headers,
            json={"text": "Hello", "client_message_id": "stable-key"},
        )
        assert response.status_code == 200
        events = [
            json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")
        ]
        assert [e["type"] for e in events] == ["delta", "done"]
        assert events[-1]["message"]["kind"] == "clarification"
        before = len([r for r in calls if r.url.path.endswith("/messages")])
        replay = c.post(
            "/api/chat/messages",
            headers=headers,
            json={"text": "Hello", "client_message_id": "stable-key"},
        )
        assert "done" in replay.text
        assert len([r for r in calls if r.url.path.endswith("/messages")]) == before
        assert (
            c.post(
                "/api/chat/messages",
                headers=headers,
                json={"text": "Changed", "client_message_id": "stable-key"},
            ).status_code
            == 409
        )
        assert (
            c.post(
                "/api/chat/messages", headers=headers, json={"text": "Hi", "tenant_id": "tenant-b"}
            ).status_code
            == 422
        )
        history = c.get("/api/chat/messages", headers=headers)
        assert history.status_code == 200
        assert history.json()[-1]["id"] == M
        assert history.json()[-1]["text"] == "Xin chào"


def test_legacy_rejects_report_and_extra_scope_before_provider(tmp_path):
    from tests.helpers import HEADERS, configured_app

    with TestClient(
        configured_app(tmp_path, lambda r: (_ for _ in ()).throw(AssertionError("provider called")))
    ) as c:
        assert c.get("/api/chat/capabilities", headers=HEADERS).json() == {
            "report_mode": False,
            "artifacts": False,
        }
        assert (
            c.post(
                "/api/chat/messages", headers=HEADERS, json={"text": "x", "output_mode": "report"}
            ).status_code
            == 422
        )
        assert (
            c.post(
                "/api/chat/messages", headers=HEADERS, json={"text": "x", "shop_id": "evil"}
            ).status_code
            == 422
        )


def test_invalid_history_order_is_recoverable_not_empty(tmp_path):
    def transport(r):
        result = handler(r)
        if r.url.path.endswith("/history"):
            body = result.json()
            item = body["items"][0]
            body["items"] = [
                item | {"id": "later", "sequence": 3},
                item | {"id": "earlier", "sequence": 2},
            ]
            return httpx.Response(200, json=body)
        return result

    with TestClient(create_app(config(tmp_path), httpx.MockTransport(transport))) as c:
        headers = login(c)
        c.post(
            "/api/chat/messages",
            headers=headers,
            json={"text": "x", "client_message_id": "stable-key"},
        )
        assert c.get("/api/chat/messages", headers=headers).status_code == 503


def test_validation_errors_do_not_echo_phone_or_claims(tmp_path):
    with TestClient(create_app(config(tmp_path), httpx.MockTransport(handler))) as c:
        result = c.post(
            "/api/chat/auth/demo-phone",
            json={"phone_number": "private-number", "user_id": "private-claim"},
        )
        assert result.status_code == 422
        assert "private-number" not in result.text and "private-claim" not in result.text


@pytest.mark.parametrize("state", ["failed", "cancelled", "reconciling", "running"])
def test_non_success_never_done_and_timeout_preserves_recovery(tmp_path, state):
    from tests.test_agent_core_contract import R

    def transport(r):
        if r.url.path == "/api/v1/runs/" + R:
            return httpx.Response(
                200, json={"run_id": R, "status": state, "response": None, "error": None}
            )
        return handler(r)

    with TestClient(create_app(config(tmp_path), httpx.MockTransport(transport))) as c:
        headers = login(c)
        c.app.state.core_chat.poll_budget = 2 if state in {"failed", "cancelled"} else 0.03
        c.app.state.core_chat.heartbeat_interval = 0.01
        result = c.post(
            "/api/chat/messages",
            headers=headers,
            json={"text": "Hello", "client_message_id": "stable-key"},
        )
        assert '"type":"done"' not in result.text
        assert '"type":"error"' in result.text
        with c.app.state.core_store.connect() as db:
            status = db.execute("SELECT status FROM core_outbox").fetchone()[0]
            assert status == (state if state in {"failed", "cancelled"} else "pending")


@pytest.mark.parametrize("case", ["malformed", "repeated", "cap"])
def test_history_cursor_validation_and_page_budget(case):
    import asyncio

    from app.agent_core import CoreAPI, CoreError

    calls = []

    def transport(request):
        calls.append(request)
        next_cursor = (
            "not-a-cursor"
            if case == "malformed"
            else (
                "00000000-0000-0000-0000-000000000001" if case == "repeated" else str(uuid.uuid4())
            )
        )
        return httpx.Response(200, json={"items": [], "next_cursor": next_cursor})

    async def exercise():
        api = CoreAPI("http://core:8000", httpx.MockTransport(transport))
        try:
            with pytest.raises(CoreError):
                await api.pages("conversations/known/history?limit=100", "server-token")
        finally:
            await api.client.aclose()

    asyncio.run(exercise())
    assert len(calls) == ({"malformed": 1, "repeated": 2, "cap": 100}[case])
