import asyncio
import json

import httpx
import pytest

from app.tools.client import PROTOCOL_VERSION, MCPClient


def test_phone_header_all_requests_no_bearer_and_session_cleanup():
    seen = []

    def handle(request):
        seen.append(request)
        if request.method == "DELETE":
            return httpx.Response(200)
        body = json.loads(request.content)
        if body["method"] == "notifications/initialized":
            return httpx.Response(202)
        result = (
            {"protocolVersion": PROTOCOL_VERSION, "capabilities": {"tools": {}}}
            if body["method"] == "initialize"
            else {"structuredContent": {"ok": True}}
        )
        return httpx.Response(
            200,
            headers={"mcp-session-id": "session"},
            json={"jsonrpc": "2.0", "id": body["id"], "result": result},
        )

    url = "http://127.0.0.1:8000/mcp"
    client = MCPClient(
        allowed_urls=frozenset({url}),
        shop_data_urls=frozenset({url}),
        allow_loopback=True,
        transport=httpx.MockTransport(handle),
    )
    assert asyncio.run(client.call_shop_tool(url, "+84900000001", "query_mart", {})) == {"ok": True}
    assert [r.method for r in seen] == ["POST", "POST", "POST", "DELETE"]
    assert all(r.headers["X-Phone-Number"] == "+84900000001" for r in seen)
    assert all("authorization" not in r.headers for r in seen)
    with pytest.raises(ValueError):
        asyncio.run(client.call_shop_tool(url, "bad\r\nheader", "query_mart", {}))


@pytest.mark.parametrize(
    "message,expected",
    [
        ("Error executing tool query_mart: permission_denied", "permission_denied"),
        ("unrecognized private diagnostic", "upstream_unavailable"),
    ],
)
def test_sdk_plain_text_error_is_sanitized_for_phone_profile(message, expected):
    from app.tools.client import ClientError

    url = "http://127.0.0.1:8000/mcp"

    def handle(request):
        if request.method == "DELETE":
            return httpx.Response(200)
        body = json.loads(request.content)
        if body["method"] == "notifications/initialized":
            return httpx.Response(202)
        result = (
            {"protocolVersion": PROTOCOL_VERSION, "capabilities": {"tools": {}}}
            if body["method"] == "initialize"
            else {"isError": True, "content": [{"type": "text", "text": message}]}
        )
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": result})

    client = MCPClient(
        allowed_urls=frozenset({url}),
        shop_data_urls=frozenset({url}),
        allow_loopback=True,
        transport=httpx.MockTransport(handle),
    )
    with pytest.raises(ClientError) as error:
        asyncio.run(client.call_shop_tool(url, "+84900000001", "query_mart", {}))
    assert error.value.code == expected
    assert str(error.value) == expected
