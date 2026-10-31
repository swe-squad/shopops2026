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
