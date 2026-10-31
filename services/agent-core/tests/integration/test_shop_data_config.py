import json
from pathlib import Path

import pytest

from app.agents.instructions import build_instructions
from app.config.registry import Registry
from app.tools.shop_bindings import Bindings


def test_shipped_data_revision_keeps_old_profiles_and_bundle_immutable():
    registry = Registry.load("config/registry.shop-data.example.json")
    legacy = Registry.load("config/registry-hosted.example.json")
    for snapshot in legacy.snapshots():
        assert registry.get(snapshot.template_id, snapshot.revision) == snapshot
    data = registry.get("shopops", "returns-hosted-data-v1")
    binding = Bindings.load("config/shop-data-bindings.example.json").get(data.shop_data_binding)
    assert binding.coverage_start == "2026-10-17"
    assert data.runtime_profile == legacy.get("shopops", "returns-hosted-v1").runtime_profile
    assert binding.phone not in build_instructions(data)
    assert "order-level return requests" in build_instructions(data)


def test_changed_binding_file_cannot_retarget_pinned_config(tmp_path):
    registry = Registry.load("config/registry.shop-data.example.json")
    data = registry.get("shopops", "returns-hosted-data-v1")
    bindings = json.loads(Path("config/shop-data-bindings.example.json").read_text())
    bindings["bindings"][0]["shop_key"] = "lazada:1001"
    path = tmp_path / "binding.json"
    path.write_text(json.dumps(bindings))
    with pytest.raises(ValueError):
        Bindings.load(str(path)).get(data.shop_data_binding)


def test_develop_registry_preserves_pins_and_provisions_chat_revision(tmp_path):
    from dotenv import dotenv_values
    from fastapi.testclient import TestClient

    from app.config.settings import Settings
    from app.main import create_app
    from tests.integration.test_runtime import environment

    path = "config/registry.shop-data.develop.example.json"
    revision = "returns-hosted-data-luna-dev-v1"
    data_url = "http://srv-captain--shop-data-mcp-dev:8000/mcp"
    core_env = dotenv_values("config/caprover-agent-core.env.example")
    chat_env = dotenv_values("config/caprover-chat-api.env.example")
    assert core_env["CONFIG_PATH"] == path
    assert chat_env["AGENT_CORE_CONFIG_REVISION"] == revision
    registry = Registry.load(path)
    legacy = Registry.load("config/registry.shop-data.example.json")
    for snapshot in legacy.snapshots():
        assert registry.get(snapshot.template_id, snapshot.revision) == snapshot
    data = registry.get("shopops", revision)
    assert data.model == core_env["OPENAI_MODEL"] == "gpt-6-luna"
    assert data.data_mcp_url == core_env["SHOP_DATA_MCP_URL"] == data_url
    assert data.knowledge_mcp_url == core_env["KNOWLEDGE_MEMORY_MCP_URL"]
    assert data.runtime_profile == legacy.get("shopops", "returns-hosted-data-v1").runtime_profile
    assert data.mcp_profile == "shop-data-read-v1"
    settings = Settings.from_env(
        core_env
        | environment(tmp_path)
        | {"CONFIG_PATH": path, "DATA_MCP_MODE": core_env["DATA_MCP_MODE"]}
    )
    # Exercise startup bundle/binding/endpoint checks and the chat provisioning API,
    # without submitting a turn or calling external services.
    with TestClient(create_app(settings=settings)) as client:
        assert client.get("/ready").status_code == 200
        request = {
            "headers": {"Authorization": "Bearer local-alice"},
            "json": {"template_id": "shopops", "config_revision": revision},
        }
        first = client.post("/api/v1/shops/shop-a/orchestrator", **request)
        assert first.status_code == 201
        assert first.json()["config_revision"] == revision
        replay = client.post("/api/v1/shops/shop-a/orchestrator", **request)
        assert replay.status_code == 200
        assert replay.json() == first.json()


def test_new_endpoint_does_not_rewrite_or_disable_old_pinned_revision(tmp_path):
    from app.composition import build_configured_bridge
    from app.config.settings import Settings
    from tests.integration.test_runtime import environment
    from tests.mcp.support import HistoryStub

    registry = Registry.load("config/registry.shop-data.example.json")
    old = registry.get("shopops", "returns-hosted-data-v1")
    new = old.model_copy(
        update={"revision": "returns-hosted-data-v2", "data_mcp_url": "http://127.0.0.1:8004/mcp"}
    )
    registry.register(new)
    settings = Settings.from_env(
        environment(tmp_path)
        | {
            "DATA_MCP_MODE": "remote",
            "SHOP_DATA_MCP_URL": new.data_mcp_url,
            "SHOP_DATA_BINDINGS_PATH": "config/shop-data-bindings.example.json",
        }
    )
    bridge = build_configured_bridge(HistoryStub(), registry, settings)
    assert old.data_mcp_url in bridge.client.shop_data_urls
    assert new.data_mcp_url in bridge.client.shop_data_urls
    assert registry.get("shopops", old.revision).data_mcp_url == old.data_mcp_url
