import asyncio

import httpx
import pytest

from app.contracts.tools import PendingToolCall
from app.tools.bridge import MCPToolBridge
from app.tools.client import ClientError, MCPClient
from app.tools.credentials import Credentials
from tests.mcp.support import KEY, SCOPE, HistoryStub, config

DATES = {"sku": "SKU-A", "start_date": "2026-10-19", "end_date": "2026-10-25"}


def pending(name: str = "get_return_metrics", arguments: dict | None = None) -> PendingToolCall:
    return PendingToolCall(
        session_id="session",
        turn_id="turn",
        call_id="call",
        name=name,
        arguments=DATES if arguments is None else arguments,
    )


async def permissions(scope, conversation_id) -> frozenset[str]:
    return frozenset({"conversation:write", "history:read"})


class TransientClient:
    """Only the network boundary is replaced for retry/failure tests."""

    def __init__(self, error: str) -> None:
        self.error = error
        self.calls = 0

    async def call_tool(self, url: str, token: str, name: str, arguments: dict) -> dict:
        self.calls += 1
        raise ClientError(self.error)


def bridge(client, repo=None) -> MCPToolBridge:
    return MCPToolBridge(
        repository=repo or HistoryStub(),
        credentials=Credentials(KEY),
        permission_resolver=permissions,
        client=client,
    )


@pytest.mark.parametrize(
    "error,count",
    [
        ("timeout", 3),
        ("upstream_unavailable", 3),
        ("permission_denied", 1),
        ("invalid_input", 1),
        ("not_found", 1),
    ],
)
def test_retry_only_transient_readonly(error: str, count: int) -> None:
    client = TransientClient(error)
    result = asyncio.run(bridge(client).execute(SCOPE, "conv-a", config(), pending()))
    assert result.error == error
    assert result.data is None
    assert client.calls == count


def test_bridge_rejects_untrusted_arguments_names_owner_and_revision_before_network() -> None:
    client = TransientClient("timeout")
    adapter = bridge(client)
    for tool_call in (
        pending("new_upstream_tool"),
        pending(arguments=DATES | {"shop_id": "shop-b"}),
    ):
        result = asyncio.run(adapter.execute(SCOPE, "conv-a", config(), tool_call))
        assert result.error == "invalid_input"
    assert (
        asyncio.run(adapter.execute(SCOPE, "conv-b", config(), pending())).error
        == "permission_denied"
    )
    assert (
        asyncio.run(adapter.execute(SCOPE, "conv-a", config(revision="changed"), pending())).error
        == "permission_denied"
    )
    assert client.calls == 0


def test_definitions_do_not_expose_unapproved_upstream_tools() -> None:
    adapter = bridge(TransientClient("timeout"))
    assert [
        d.name for d in adapter.definitions(config(capabilities=("search_knowledge", "new_tool")))
    ] == ["search_knowledge"]


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://internal/mcp",
        "http://169.254.169.254/mcp",
        "http://[::ffff:169.254.169.254]/mcp",
        "http://[fd00:ec2::254]/mcp",
        "http://metadata.google.internal/mcp",
        "http://instance-data/latest/meta-data",
        "http://127.0.0.1/mcp#fragment",
        "http://user:password@internal/mcp",
        "http://0.0.0.0/mcp",
    ],
)
def test_unsafe_endpoints_rejected_even_when_allowlisted(url: str) -> None:
    with pytest.raises(ValueError):
        MCPClient(allowed_urls=frozenset({url}), allow_loopback=True)


def test_missing_remote_auth_and_urls_fail_profile_validation() -> None:
    adapter = bridge(TransientClient("timeout"))
    for snapshot in (config(mcp_profile="remote-v1"), config(data_mcp_url="")):
        with pytest.raises(ValueError):
            adapter.validate_profile(snapshot)


def test_timeout_is_total_and_cancels_hung_client() -> None:
    class Hanging:
        async def call_tool(self, *args):
            await asyncio.sleep(10)

    result = asyncio.run(
        MCPToolBridge(
            repository=HistoryStub(),
            credentials=Credentials(KEY),
            permission_resolver=permissions,
            client=Hanging(),
            timeout_seconds=0.01,
        ).execute(SCOPE, "conv-a", config(), pending())
    )
    assert result.error == "timeout"


def test_client_refuses_unlisted_url_before_io() -> None:
    client = MCPClient(
        allowed_urls=frozenset({"http://127.0.0.1:8000/mcp/data"}), allow_loopback=True
    )
    with pytest.raises(ClientError) as exc:
        asyncio.run(client.call_tool("http://unapproved/mcp", "token", "get_return_metrics", DATES))
    assert exc.value.code == "invalid_input"


def test_client_does_not_follow_redirects_or_leak_token() -> None:
    requests = []

    def redirect(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(307, headers={"Location": "http://169.254.169.254/mcp"})

    url = "http://127.0.0.1:8000/mcp/data"
    client = MCPClient(
        allowed_urls=frozenset({url}), allow_loopback=True, transport=httpx.MockTransport(redirect)
    )
    with pytest.raises(ClientError) as exc:
        asyncio.run(client.call_tool(url, "test-token", "get_return_metrics", DATES))
    assert exc.value.code == "invalid_input"
    assert len(requests) == 1


def test_malformed_output_is_not_retried() -> None:
    class Malformed:
        calls = 0

        async def call_tool(self, *args):
            self.calls += 1
            return {"data": {"orders": 100, "returns": 15}}

    client = Malformed()
    result = asyncio.run(bridge(client).execute(SCOPE, "conv-a", config(), pending()))
    assert result.error == "upstream_unavailable"
    assert client.calls == 1


@pytest.mark.parametrize(
    "mode,code,retryable",
    [
        ("json-malformed", "upstream_unavailable", False),
        ("wrong-id", "upstream_unavailable", False),
        ("tool-error-text", "upstream_unavailable", False),
        ("huge-wire", "upstream_unavailable", False),
        ("forbidden", "permission_denied", False),
        ("unavailable", "upstream_unavailable", True),
    ],
)
def test_protocol_errors_are_sanitized(mode: str, code: str, retryable: bool) -> None:
    import json

    def respond(request: httpx.Request) -> httpx.Response:
        message = json.loads(request.content)
        if mode == "forbidden":
            return httpx.Response(403)
        if mode == "unavailable":
            return httpx.Response(503)
        if mode == "json-malformed":
            return httpx.Response(
                200, content=b"bad-json", headers={"Content-Type": "application/json"}
            )
        if mode == "wrong-id":
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": 999, "result": {}})
        if mode == "huge-wire":
            return httpx.Response(
                200, content=b"x" * 300000, headers={"Content-Type": "application/json"}
            )
        if message["method"] == "initialize":
            result = {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}}}
        elif message["method"] == "notifications/initialized":
            return httpx.Response(202)
        else:
            result = {
                "isError": True,
                "content": [{"type": "text", "text": "sensitive server error"}],
            }
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": message["id"], "result": result})

    url = "http://127.0.0.1:8000/mcp"
    client = MCPClient(
        allowed_urls=frozenset({url}), allow_loopback=True, transport=httpx.MockTransport(respond)
    )
    with pytest.raises(ClientError) as exc:
        asyncio.run(client.call_tool(url, "token", "search_knowledge", {"query": "sizing"}))
    assert exc.value.code == code
    assert exc.value.retryable is retryable
    assert "sensitive" not in str(exc.value)


@pytest.mark.parametrize("include_safe_first", [False, True])
def test_dns_metadata_resolution_is_rejected_before_connect(
    monkeypatch, include_safe_first: bool
) -> None:
    import socket

    async def exercise():
        async def malicious_dns(*args, **kwargs):
            unsafe = (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 80))
            safe = (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 80))
            return [safe, unsafe] if include_safe_first else [unsafe]

        monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", malicious_dns)
        client = MCPClient(allowed_urls=frozenset({"http://approved.internal/mcp"}))
        with pytest.raises(ClientError) as exc:
            await client.call_tool(
                "http://approved.internal/mcp", "token", "get_return_metrics", DATES
            )
        assert exc.value.code == "invalid_input"

    asyncio.run(exercise())


def test_bridge_rejects_cross_conversation_history_from_remote() -> None:
    from app.contracts.models import Source
    from app.contracts.tools import ToolResult

    repo = HistoryStub()
    message = repo.messages["conv-b"][0]

    class WrongHistory:
        async def call_tool(self, *args):
            return ToolResult(
                data={"messages": [message.model_dump(mode="json")]},
                sources=(Source(type="history", reference=f"history:conv-b:{message.id}"),),
                observed_at="2026-10-25T00:00:00Z",
            ).model_dump(mode="json")

    result = asyncio.run(
        bridge(WrongHistory(), repo).execute(
            SCOPE,
            "conv-a",
            config(),
            pending("get_conversation_history", {"before_sequence": None, "limit": 1}),
        )
    )
    assert result.error == "upstream_unavailable"
    assert result.data is None


def test_bridge_rejects_wrong_bundle_and_excess_matches() -> None:
    from app.contracts.models import Source
    from app.contracts.tools import ToolResult

    class WrongBundle:
        async def call_tool(self, *args):
            return ToolResult(
                data={
                    "matches": [
                        {
                            "bundle_id": "other",
                            "version": "2",
                            "document_id": "sizing",
                            "chunk_id": "1",
                            "excerpt": "sizing",
                        }
                    ]
                },
                sources=(Source(type="knowledge", reference="knowledge:other:2:sizing#1"),),
                observed_at="2026-10-25T00:00:00Z",
            ).model_dump(mode="json")

    result = asyncio.run(
        bridge(WrongBundle()).execute(
            SCOPE, "conv-a", config(), pending("search_knowledge", {"query": "sizing", "limit": 1})
        )
    )
    assert result.error == "upstream_unavailable"


@pytest.mark.parametrize("fail_after_init", [True, False])
def test_mcp_session_cleanup_on_failure_and_bounded_delete_body(fail_after_init: bool) -> None:
    import json

    deleted = []

    class UnreadBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            raise AssertionError("DELETE response must not be buffered")
            yield b"unreachable"

    def respond(request: httpx.Request) -> httpx.Response:
        if request.method == "DELETE":
            deleted.append(request.headers.get("mcp-session-id"))
            return httpx.Response(200, stream=UnreadBody())
        message = json.loads(request.content)
        if message["method"] == "initialize":
            return httpx.Response(
                200,
                headers={"Mcp-Session-Id": "cleanup-test"},
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}}},
                },
            )
        if fail_after_init:
            return httpx.Response(403)
        if message["method"] == "notifications/initialized":
            return httpx.Response(202)
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "result": {
                    "content": [],
                    "structuredContent": {
                        "schema_version": "1",
                        "data": {"matches": []},
                        "sources": [],
                        "observed_at": "2026-10-25T00:00:00Z",
                        "error": None,
                    },
                    "isError": False,
                },
            },
        )

    url = "http://127.0.0.1:8000/mcp"
    client = MCPClient(
        allowed_urls=frozenset({url}), allow_loopback=True, transport=httpx.MockTransport(respond)
    )
    if fail_after_init:
        with pytest.raises(ClientError) as exc:
            asyncio.run(client.call_tool(url, "token", "search_knowledge", {"query": "sizing"}))
        assert exc.value.code == "permission_denied"
    else:
        result = asyncio.run(
            client.call_tool(url, "token", "search_knowledge", {"query": "sizing"})
        )
        assert result["data"] == {"matches": []}
    assert deleted == ["cleanup-test"]


def test_default_bridge_uses_run_grants_and_compares_identity_without_grants() -> None:
    repo = HistoryStub()
    scope = SCOPE.model_copy(update={"permissions": frozenset({"conversation:write"})})
    client = TransientClient("not_found")
    adapter = MCPToolBridge(repository=repo, credentials=Credentials(KEY), client=client)
    result = asyncio.run(adapter.execute(scope, "conv-a", config(), pending()))
    assert result.error == "not_found"
    assert client.calls == 1
    empty = scope.model_copy(update={"permissions": frozenset()})
    denied = asyncio.run(adapter.execute(empty, "conv-a", config(), pending()))
    assert denied.error == "permission_denied"


def test_permission_resolver_can_only_restrict_run_grants() -> None:
    repo = HistoryStub()
    scope = SCOPE.model_copy(update={"permissions": frozenset({"conversation:write"})})
    repo.conversations["conv-a"] = repo.conversations["conv-a"].model_copy(update={"scope": scope})
    client = TransientClient("not_found")
    adapter = MCPToolBridge(
        repository=repo,
        credentials=Credentials(KEY),
        client=client,
        permission_resolver=permissions,
    )
    result = asyncio.run(
        adapter.execute(
            scope, "conv-a", config(), pending("get_conversation_history", {"limit": 1})
        )
    )
    assert result.error == "permission_denied"
    assert client.calls == 0
