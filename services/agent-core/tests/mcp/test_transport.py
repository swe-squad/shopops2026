import asyncio
import json
import socket
import threading
import time
from contextlib import contextmanager

import pytest
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

from app.mcp.data import build_data_app
from app.mcp.knowledge_memory import build_knowledge_memory_app
from app.tools.bridge import MCPToolBridge
from app.tools.client import ClientError, MCPClient
from app.tools.credentials import Credentials
from tests.mcp.support import KEY, OTHER_SHOP, OTHER_USER, SCOPE, HistoryStub, config
from tests.tools.test_bridge import pending, permissions


@contextmanager
def serve(app: FastAPI):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(128)
    address = f"http://127.0.0.1:{sock.getsockname()[1]}"
    server = uvicorn.Server(
        uvicorn.Config(app, log_config=None, access_log=False, loop="asyncio", lifespan="off")
    )
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while not server.started:
            if not thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError("loopback server did not start")
            time.sleep(0.01)
        yield address
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()
        assert not thread.is_alive(), "loopback server did not stop"


def test_real_http_both_servers_scope_history_and_bundle() -> None:
    repo = HistoryStub()
    credentials = Credentials(KEY)
    app = FastAPI()
    app.mount("/mcp/data", build_data_app(repository=repo, credentials=credentials))
    app.mount(
        "/mcp/knowledge-memory",
        build_knowledge_memory_app(repository=repo, credentials=credentials),
    )
    with serve(app) as base:
        snapshot = config(
            base,
            data_mcp_url=base + "/mcp/data/",
            knowledge_mcp_url=base + "/mcp/knowledge-memory/",
        )
        for cid, conversation in repo.conversations.items():
            repo.conversations[cid] = conversation.model_copy(update={"config": snapshot})
        client = MCPClient(
            allowed_urls=frozenset({snapshot.data_mcp_url, snapshot.knowledge_mcp_url}),
            allow_loopback=True,
        )
        bridge = MCPToolBridge(
            repository=repo, credentials=credentials, permission_resolver=permissions, client=client
        )

        async def exercise():
            metrics = await bridge.execute(SCOPE, "conv-a", snapshot, pending())
            assert metrics.error is None
            assert metrics.data["return_rate"] == 15
            assert metrics.data["baseline"]["return_rate"] == 5
            assert metrics.data["change_percentage_points"] == 10
            search = await bridge.execute(
                SCOPE,
                "conv-a",
                snapshot,
                pending("search_knowledge", {"query": "sizing", "limit": 2}),
            )
            assert search.error is None
            assert search.data["matches"][0]["version"] == "1"
            history = await bridge.execute(
                SCOPE,
                "conv-a",
                snapshot,
                pending("get_conversation_history", {"before_sequence": 4, "limit": 2}),
            )
            assert [m["sequence"] for m in history.data["messages"]] == [2, 3]
            assert all(m["conversation_id"] == "conv-a" for m in history.data["messages"])
            # Bypass bridge preflight with a correctly signed wrong-scope token.
            for owner in (OTHER_SHOP, OTHER_USER):
                token = credentials.issue(
                    owner, "conv-a", snapshot.revision, "agent-core:data", {"conversation:write"}
                )
                with pytest.raises(ClientError) as exc:
                    await client.call_tool(
                        snapshot.data_mcp_url, token, "get_return_metrics", pending().arguments
                    )
                assert exc.value.code == "permission_denied"
            bad_bundle = snapshot.model_copy(update={"knowledge_version": "nonexistent"})
            repo.conversations["conv-a"] = repo.conversations["conv-a"].model_copy(
                update={"config": bad_bundle}
            )
            result = await bridge.execute(
                SCOPE,
                "conv-a",
                bad_bundle,
                pending("search_knowledge", {"query": "sizing", "limit": 1}),
            )
            assert result.error == "not_found"

        asyncio.run(exercise())


def test_sse_response_session_lifecycle_and_text_result() -> None:
    app = FastAPI()
    sessions = []

    @app.api_route("/mcp", methods=["POST", "DELETE"])
    async def mcp(request: Request):
        from fastapi.responses import Response

        if request.method == "DELETE":
            sessions.append((request.method, request.headers.get("mcp-session-id")))
            return Response(status_code=200)
        message = await request.json()
        if message["method"] == "notifications/initialized":
            assert request.headers["mcp-session-id"] == "session-1"
            return Response(status_code=202)
        if message["method"] == "initialize":
            result = {
                "protocolVersion": "2025-06-18",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "reference-test-server", "version": "1"},
            }
        else:
            assert request.headers["mcp-session-id"] == "session-1"
            result = {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "schema_version": "1",
                                "data": {"matches": []},
                                "sources": [],
                                "observed_at": "2026-10-25T00:00:00Z",
                                "error": None,
                            }
                        ),
                    }
                ],
                "isError": False,
            }
        wire = (
            "event: message\r\ndata: "
            + json.dumps({"jsonrpc": "2.0", "id": message["id"], "result": result})
            + "\r\n\r\n"
        ).encode()

        async def stream():
            yield b": keepalive\n\n"
            for i in range(0, len(wire), 7):
                yield wire[i : i + 7]

        return StreamingResponse(
            stream(), media_type="text/event-stream", headers={"Mcp-Session-Id": "session-1"}
        )

    with serve(app) as base:
        client = MCPClient(allowed_urls=frozenset({base + "/mcp"}), allow_loopback=True)
        result = asyncio.run(
            client.call_tool(
                base + "/mcp", "test-token", "search_knowledge", {"query": "unknown", "limit": 1}
            )
        )
        assert result["data"] == {"matches": []}
        assert sessions == [("DELETE", "session-1")]


def test_old_and_new_conversations_keep_pinned_endpoint_profiles() -> None:
    old_repo, new_repo = HistoryStub(), HistoryStub()
    credentials = Credentials(KEY)
    with (
        serve(build_data_app(repository=old_repo, credentials=credentials)) as old_url,
        serve(build_data_app(repository=new_repo, credentials=credentials)) as new_url,
    ):
        old = config(data_mcp_url=old_url + "/", knowledge_mcp_url=old_url + "/")
        new = config(
            revision="returns-v2",
            mcp_profile="remote-v1",
            data_mcp_url=new_url + "/",
            knowledge_mcp_url=new_url + "/",
        )
        old_repo.conversations["conv-a"] = old_repo.conversations["conv-a"].model_copy(
            update={"config": old}
        )
        new_repo.conversations["conv-a"] = new_repo.conversations["conv-a"].model_copy(
            update={"id": "conv-new", "config": new}
        )
        old_repo.conversations["conv-new"] = new_repo.conversations.pop("conv-a")
        new_repo.conversations["conv-new"] = old_repo.conversations["conv-new"]
        client = MCPClient(
            allowed_urls=frozenset({old.data_mcp_url, new.data_mcp_url}), allow_loopback=True
        )
        bridge = MCPToolBridge(
            repository=old_repo,
            credentials=credentials,
            client=client,
            permission_resolver=permissions,
            compatible_remote_profiles=frozenset({"remote-v1"}),
        )

        async def exercise():
            a = await bridge.execute(SCOPE, "conv-a", old, pending())
            b = await bridge.execute(SCOPE, "conv-new", new, pending())
            assert a.error is None and b.error is None
            assert old_repo.conversations["conv-a"].config.mcp_profile == "mock-v1"
            assert old_repo.conversations["conv-new"].config.mcp_profile == "remote-v1"
            assert old_repo.conversations["conv-a"].config.data_mcp_url == old_url + "/"

        asyncio.run(exercise())
