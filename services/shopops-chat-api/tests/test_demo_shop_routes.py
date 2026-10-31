import hashlib
import json
from dataclasses import replace

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings
from tests.test_demo_phone_auth import config, login


def routes():
    return {
        f"local-demo-{n:03}": {
            "shop_id": f"shop-demo-{n:03}",
            "config_revision": f"returns-hosted-data-luna-shop{n:03}-dev-v1",
        }
        for n in range(2, 5)
    }


def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_CORE_DEMO_ROUTES_JSON", json.dumps(routes()))
    loaded = Settings.from_env()
    return replace(config(tmp_path), core_routes=loaded.core_routes)


def test_four_logins_route_and_restart_without_provider_input(tmp_path, monkeypatch):
    configured = settings(tmp_path, monkeypatch)
    calls = []

    def core(request):
        calls.append(request)
        token = request.headers["Authorization"].removeprefix("Bearer ")
        route = routes().get(token, {"shop_id": "shop-a", "config_revision": "v1"})
        assert request.method == "POST"
        assert request.url.path == f"/api/v1/shops/{route['shop_id']}/orchestrator"
        assert json.loads(request.content)["config_revision"] == route["config_revision"]
        return httpx.Response(
            200,
            json={
                "orchestrator_id": "orchestrator-" + token,
                "config_revision": route["config_revision"],
            },
        )

    with TestClient(create_app(configured, httpx.MockTransport(core))) as client:
        headers = [login(client, f"+849000000{n:02}") for n in range(1, 5)]
        assert len(calls) == 4
        for value in headers:
            response = client.get("/api/chat/messages", headers=value)
            assert response.status_code == 200
            assert response.json() == []
        assert (
            client.post(
                "/api/chat/auth/demo-phone", json={"phone_number": "+84900000005"}
            ).status_code
            == 401
        )
        with client.app.state.core_store.connect() as db:
            spaces = db.execute("SELECT * FROM core_spaces").fetchall()
        assert len({row["namespace"] for row in spaces}) == 4
        actor = json.dumps(["tenant-a", "alice"])
        configuration = json.dumps(["http://core:8000", "shop-a", "v1"])
        old_namespace = hashlib.sha256((actor + configuration).encode()).hexdigest()
        assert old_namespace in {row["namespace"] for row in spaces}

    with TestClient(create_app(configured, httpx.MockTransport(core))) as client:
        for value in headers:
            assert client.get("/api/chat/messages", headers=value).status_code == 200
        for n in range(1, 5):
            login(client, f"+849000000{n:02}")
        assert len(calls) == 4


def test_route_cannot_expand_identity_grants(tmp_path, monkeypatch):
    mapping = routes()
    mapping["local-demo-002"]["shop_id"] = "shop-a"
    monkeypatch.setenv("AGENT_CORE_DEMO_ROUTES_JSON", json.dumps(mapping))
    configured = replace(config(tmp_path), core_routes=Settings.from_env().core_routes)

    def forbidden(request):
        raise AssertionError("Unauthorized shop must be rejected before Core I/O")

    with TestClient(create_app(configured, httpx.MockTransport(forbidden))) as client:
        assert (
            client.post(
                "/api/chat/auth/demo-phone", json={"phone_number": "+84900000002"}
            ).status_code
            == 404
        )


def test_new_accounts_cannot_use_original_workspace_navigation(tmp_path, monkeypatch):
    from tests.test_agent_core_contract import handler

    configured = replace(settings(tmp_path, monkeypatch), token="server-only")

    def transport(request):
        assert request.url.host == "core", "Must not forward to the original shop workspace"
        route = routes().get(request.headers["Authorization"].removeprefix("Bearer "))
        if route:
            return httpx.Response(
                200,
                json={
                    "orchestrator_id": "demo-orchestrator",
                    "config_revision": route["config_revision"],
                },
            )
        return handler(request)

    with TestClient(create_app(configured, httpx.MockTransport(transport))) as client:
        for number in range(2, 5):
            headers = login(client, f"+849000000{number:02}")
            assert (
                client.post(
                    "/api/chat/navigation", headers=headers, json={"url": "/shop/incidents"}
                ).status_code
                == 403
            )


def test_four_accounts_send_same_client_key_to_separate_conversations(tmp_path, monkeypatch):
    configured = settings(tmp_path, monkeypatch)
    seen = set()

    def core(request):
        token = request.headers["Authorization"].removeprefix("Bearer ")
        route = routes().get(token, {"shop_id": "shop-a", "config_revision": "v1"})
        body = json.loads(request.content) if request.content else {}
        conversation, run, message = (prefix + token for prefix in ("conv-", "run-", "msg-"))
        artifact = "artifact-" + token
        content = ("# Synthetic report " + token).encode()
        path = request.url.path
        if path.endswith("/orchestrator"):
            assert path == f"/api/v1/shops/{route['shop_id']}/orchestrator"
            return httpx.Response(
                200,
                json={
                    "orchestrator_id": "orch-" + token,
                    "config_revision": route["config_revision"],
                },
            )
        if path.endswith("/conversations"):
            assert path == f"/api/v1/shops/{route['shop_id']}/conversations"
            assert body["expected_config_revision"] == route["config_revision"]
            return httpx.Response(201, json={"conversation_id": conversation})
        if path.endswith("/messages"):
            assert path == f"/api/v1/conversations/{conversation}/messages"
            assert body["client_message_id"] == "same-key"
            seen.add(token)
            return httpx.Response(202, json={"message_id": message, "run_id": run})
        if path.endswith("/history"):
            assert path == f"/api/v1/conversations/{conversation}/history"
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": message,
                            "conversation_id": conversation,
                            "run_id": run,
                            "role": "assistant",
                            "content": "Own reply",
                            "sequence": 2,
                            "created_at": "2026-10-31T12:00:00Z",
                        }
                    ],
                    "next_cursor": None,
                },
            )
        if path.endswith("/artifacts"):
            assert path == f"/api/v1/runs/{run}/artifacts"
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": artifact,
                            "run_id": run,
                            "filename": "report.md",
                            "media_type": "text/markdown",
                            "size": len(content),
                            "sha256": hashlib.sha256(content).hexdigest(),
                            "availability": "available",
                        }
                    ],
                    "next_cursor": None,
                },
            )
        if path.endswith("/content"):
            assert path == f"/api/v1/artifacts/{artifact}/content"
            return httpx.Response(200, content=content, headers={"Content-Type": "text/markdown"})
        assert path == f"/api/v1/runs/{run}"
        return httpx.Response(
            200,
            json={
                "run_id": run,
                "status": "completed",
                "response": {"kind": "clarification", "text": "Own reply", "sources": []},
                "error": None,
            },
        )

    # Persist Alice's real outbox, conversation and artifact using the pre-routing configuration.
    with TestClient(
        create_app(replace(configured, core_routes={}), httpx.MockTransport(core))
    ) as old:
        original_headers = login(old)
        original = old.post(
            "/api/chat/messages",
            headers=original_headers,
            json={"text": "Hello", "client_message_id": "same-key"},
        )
        assert '"type":"done"' in original.text

    with TestClient(create_app(configured, httpx.MockTransport(core))) as client:
        assert client.get("/api/chat/messages", headers=original_headers).status_code == 200
        headers = [login(client, f"+849000000{n:02}") for n in range(1, 5)]
        own_messages = []
        artifacts = []
        for value in headers:
            result = client.post(
                "/api/chat/messages",
                headers=value,
                json={"text": "Hello", "client_message_id": "same-key"},
            )
            events = [
                json.loads(line[6:])
                for line in result.text.splitlines()
                if line.startswith("data: ")
            ]
            assert events[-1]["type"] == "done", events
            own_messages.append(events[-1]["message"]["id"])
            artifacts.append(events[-1]["message"]["artifacts"][0]["id"])
        assert len(seen) == len(set(own_messages)) == 4
        for value, message in zip(headers, own_messages, strict=True):
            history = client.get("/api/chat/messages", headers=value)
            assert history.status_code == 200
            assert [item["id"] for item in history.json()] == [message]
            assert (
                client.get("/api/chat/artifacts/foreign/content", headers=value).status_code == 404
            )
        for index, value in enumerate(headers):
            for other, artifact_id in enumerate(artifacts):
                result = client.get(f"/api/chat/artifacts/{artifact_id}/content", headers=value)
                assert result.status_code == (200 if index == other else 404)


@pytest.mark.parametrize(
    "value",
    [
        "[]",
        "null",
        "{",
        '{"local-demo-002": {}}',
        '{"local-demo-002":{"shop_id":"../shop-a","config_revision":"v1"}}',
        '{"local-demo-002":{"shop_id":"shop-a","config_revision":"v1","extra":1}}',
    ],
)
def test_invalid_route_config_fails_closed(monkeypatch, value):
    monkeypatch.setenv("AGENT_CORE_DEMO_ROUTES_JSON", value)
    with pytest.raises((ValueError, RuntimeError)):
        Settings.from_env()
