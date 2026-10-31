"""All four delivered modules over real HTTP; OpenAI is replaced by its fake provider."""

import json
import socket
import threading
import time
from contextlib import contextmanager

import httpx
import uvicorn

from app.config.settings import Settings
from app.main import create_app
from app.providers.fake import FakeProvider, Scenario
from tests.integration.test_runtime import environment
from tests.integration.test_task_integration import completed, start_conversation


@contextmanager
def running_service(app, sock):
    server = uvicorn.Server(
        uvicorn.Config(app, log_config=None, access_log=False, loop="asyncio", lifespan="on")
    )
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while not server.started:
            if not thread.is_alive() or time.monotonic() >= deadline:
                raise AssertionError("Integrated service did not start")
            time.sleep(0.01)
        yield
    finally:
        server.should_exit = True
        thread.join(5)
        assert not thread.is_alive(), "Integrated service did not stop"


def test_all_modules_with_real_http_mcp_and_sqlite(tmp_path):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(128)
        base = f"http://127.0.0.1:{sock.getsockname()[1]}"
        registry = json.loads(open("config/registry.json").read())
        # Keep the v1 exact-path URLs; the client deliberately does not follow redirects.
        for revision in registry["revisions"]:
            revision["data_mcp_url"] = base + "/mcp/data"
            revision["knowledge_mcp_url"] = base + "/mcp/knowledge-memory"
        registry_path = tmp_path / "registry.json"
        registry_path.write_text(json.dumps(registry))
        settings = Settings.from_env(
            environment(tmp_path)
            | {
                "CONFIG_PATH": str(registry_path),
                "DATA_MCP_URL": base + "/mcp/data",
                "KNOWLEDGE_MEMORY_MCP_URL": base + "/mcp/knowledge-memory",
            }
        )
        provider = FakeProvider(
            [
                Scenario(
                    tool_name="get_return_metrics",
                    arguments={
                        "sku": "SKU-A",
                        "start_date": "2026-10-19",
                        "end_date": "2026-10-25",
                    },
                ),
                Scenario(tool_name="search_knowledge", arguments={"query": "sizing", "limit": 2}),
                Scenario(tool_name="get_conversation_history", arguments={"limit": 4}),
                Scenario(),
            ]
        )
        app = create_app(settings=settings, provider=provider)
        with (
            running_service(app, sock),
            httpx.Client(
                base_url=base,
                headers={"Authorization": "Bearer local-alice"},
                timeout=5,
                trust_env=False,
            ) as client,
        ):
            assert client.get("/api/v1/ready").status_code == 200
            conversation_id = start_conversation(client)
            path = f"/api/v1/conversations/{conversation_id}/messages"
            responses = []
            for n in range(4):
                submitted = client.post(
                    path, json={"client_message_id": f"m{n}", "content": f"step {n}"}
                )
                assert submitted.status_code == 202, submitted.text
                result = completed(client, submitted.json()["run_id"])
                responses.append(result["response"])
            assert responses[0]["sources"][0]["type"] == "data"
            assert '"return_rate": 15' in responses[0]["text"]
            assert '"return_rate": 5' in responses[0]["text"]
            assert '"change_percentage_points": 10' in responses[0]["text"]
            assert responses[1]["sources"][0]["type"] == "knowledge"
            assert responses[2]["sources"][0]["type"] == "history"
            assert responses[3]["kind"] == "clarification"
            assert len(provider.sessions) == 1
            assert (
                len(client.get(f"/api/v1/conversations/{conversation_id}/history").json()["items"])
                == 8
            )
            assert (
                client.get(
                    f"/api/v1/conversations/{conversation_id}/history",
                    headers={"Authorization": "Bearer local-bob"},
                ).status_code
                == 404
            )
            # Authenticated application tokens are not scoped MCP credentials.
            assert client.post("/mcp/data", json={}).status_code == 401


def test_unapproved_remote_profile_fails_before_application_becomes_ready(tmp_path):
    from dataclasses import replace

    import pytest
    from fastapi.testclient import TestClient

    registry = json.loads(open("config/registry.json").read())
    registry["revisions"][0]["mcp_profile"] = "remote-unapproved"
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(registry))
    settings = replace(Settings.from_env(environment(tmp_path)), config_path=str(path))
    with pytest.raises(ValueError, match="compatibility approval"):
        with TestClient(create_app(settings=settings)):
            pass


def test_revision_activation_requires_remote_profile_approval(tmp_path, monkeypatch):
    import argparse
    import asyncio

    import pytest

    from app.config.registry import Registry
    from app.storage.database import Database
    from app.storage.repositories import SQLiteRepository
    from scripts.activate_revision import activate

    registry = json.loads(open("config/registry.json").read())
    registry["revisions"].append(
        registry["revisions"][0] | {"revision": "new", "mcp_profile": "unapproved"}
    )
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(registry))
    env = environment(tmp_path) | {"CONFIG_PATH": str(path)}
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    database = Database(Settings.from_env(env).database_path)
    asyncio.run(database.initialize())
    repo = SQLiteRepository(database, Registry.load(str(path)))
    from app.contracts.identity import Scope

    asyncio.run(
        repo.provision(Scope(tenant_id="t", shop_id="s", user_id="u"), "shopops", "returns-v1")
    )
    args = argparse.Namespace(tenant="t", shop="s", user="u", template="shopops", revision="new")
    with pytest.raises(ValueError, match="compatibility approval"):
        asyncio.run(activate(args))
