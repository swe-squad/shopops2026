import json
from dataclasses import replace

import httpx
from fastapi.testclient import TestClient

from app.main import create_app
from tests.test_agent_core_contract import handler
from tests.test_demo_phone_auth import config, login


def test_navigation_server_token_no_chat_resubmit(tmp_path):
    calls = []

    def transport(r):
        calls.append(r)
        if r.url.host == "shop":
            assert r.headers["Authorization"] == "Bearer server-only"
            assert json.loads(r.content) == {"url": "/shop/incidents"}
            return httpx.Response(202)
        return handler(r)

    with TestClient(
        create_app(replace(config(tmp_path), token="server-only"), httpx.MockTransport(transport))
    ) as c:
        assert c.post("/api/chat/navigation", json={"url": "/shop/incidents"}).status_code == 401
        headers = login(c)
        for _ in range(2):
            assert (
                c.post(
                    "/api/chat/navigation", headers=headers, json={"url": "/shop/incidents"}
                ).status_code
                == 204
            )
        for url in [
            "https://user:pass@evil/shop/x",
            "//evil/shop/x",
            "/shop/../private",
            "/shop/%2e%2e/private",
            "/api/chat/artifacts/x/content",
        ]:
            assert (
                c.post("/api/chat/navigation", headers=headers, json={"url": url}).status_code
                == 422
            )
        assert len(calls) == 3


def test_navigation_preserves_allowed_external_links_and_shop_fragments(tmp_path):
    calls = []

    def transport(r):
        if r.url.host == "shop":
            calls.append(json.loads(r.content)["url"])
            return httpx.Response(201)
        return handler(r)

    with TestClient(
        create_app(replace(config(tmp_path), token="server-only"), httpx.MockTransport(transport))
    ) as c:
        headers = login(c)
        for url in ["https://example.com/tracking", "/shop/incidents#late"]:
            assert (
                c.post("/api/chat/navigation", headers=headers, json={"url": url}).status_code
                == 204
            )
        assert len(calls) == 2
