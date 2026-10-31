import json
from pathlib import Path

import pytest

from app.agents.runtime_bundle import build_runtime_bundle
from app.config.registry import Registry
from app.config.settings import Settings
from app.providers.hosted_runtime import build_hosted_environment
from tests.integration.test_runtime import environment


def test_registered_hosted_example_builds_real_plugin():
    registry = Registry.load("config/registry-hosted.example.json")
    config = next(
        c for c in registry.snapshots() if c.runtime_profile.environment_type == "openai_hosted"
    )
    manifest = json.loads(Path("runtime-bundles/shopops-hosted-v1/manifest.json").read_text())
    assert config.runtime_profile.bundle_sha256 == manifest["bundle_sha256"]
    assert config.runtime_profile.bundle_version == manifest["bundle_version"]
    assert config.model != "fixture-only"
    result = build_hosted_environment(
        config.runtime_profile, build_runtime_bundle(config.runtime_profile)
    )
    assert result["network"] == {"access": "disabled"}
    assert len(result["plugins"]) == 1


def test_investigation_revision_is_opt_in_and_preserves_existing_pins():
    registry = Registry.load("config/registry-hosted.example.json")
    old = registry.get("shopops", "returns-hosted-v1")
    new = registry.get("shopops", "returns-hosted-v2")
    assert old.runtime_profile.bundle_version == "1.0.0"
    assert new.runtime_profile.bundle_version == "1.1.0"
    manifest = json.loads(Path("runtime-bundles/shopops-hosted-v1.1/manifest.json").read_text())
    assert new.runtime_profile.bundle_sha256 == manifest["bundle_sha256"]
    assert old.capabilities == new.capabilities
    assert old.mcp_profile == new.mcp_profile == "mock-v1"
    assert old.data_mcp_url == new.data_mcp_url
    assert old.knowledge_mcp_url == new.knowledge_mcp_url
    assert Registry.load("config/registry.json").snapshots() == (
        registry.get("shopops", "returns-v1"),
    )
    for config in (old, new):
        assert build_hosted_environment(
            config.runtime_profile, build_runtime_bundle(config.runtime_profile)
        )["network"] == {"access": "disabled"}


def test_missing_configured_bundle_path_is_rejected_before_provider_io(tmp_path, repo):
    from app.composition import build_configured_provider

    values = environment(tmp_path) | {
        "AGENT_PROVIDER": "openai_agents",
        "OPENAI_API_KEY": "synthetic",
        "OPENAI_MODEL": "synthetic",
        "RUNTIME_BUNDLE_PATH": "missing-runtime-bundles",
    }
    with pytest.raises(ValueError, match="RUNTIME_BUNDLE_PATH"):
        build_configured_provider(Settings.from_env(values), repo)


@pytest.mark.parametrize("value", ["", "../runtime-bundles", "/etc"])
def test_runtime_bundle_path_stays_in_service(tmp_path, repo, value):
    from app.composition import build_configured_provider

    values = environment(tmp_path) | {
        "AGENT_PROVIDER": "openai_agents",
        "OPENAI_API_KEY": "synthetic",
        "OPENAI_MODEL": "synthetic",
        "RUNTIME_BUNDLE_PATH": value,
    }
    with pytest.raises(ValueError, match="RUNTIME_BUNDLE_PATH"):
        build_configured_provider(Settings.from_env(values), repo)


def test_configured_provider_uses_selected_bundle_directory(tmp_path, repo, monkeypatch):
    import asyncio
    import shutil
    from types import SimpleNamespace

    import openai

    from app.agents import runtime_bundle
    from app.composition import build_configured_provider

    selected = tmp_path / "selected-bundles"
    shutil.copytree("runtime-bundles", selected)
    monkeypatch.setattr(Settings, "runtime_bundle_root", property(lambda self: selected))
    monkeypatch.setattr(runtime_bundle, "BUNDLE_ROOT", tmp_path / "missing-default")
    captured = []

    async def create_session(**request):
        captured.append(request)
        return {"id": "session", "environment": {"type": "openai_hosted", "id": "env"}}

    client = SimpleNamespace(
        beta=SimpleNamespace(
            agents=SimpleNamespace(sessions=SimpleNamespace(create=create_session))
        )
    )
    monkeypatch.setattr(openai, "AsyncOpenAI", lambda **kwargs: client)
    values = environment(tmp_path) | {
        "AGENT_PROVIDER": "openai_agents",
        "OPENAI_API_KEY": "synthetic",
        "OPENAI_MODEL": "gpt-6-astra",
        "RUNTIME_BUNDLE_PATH": "selected-bundles",
    }
    provider = build_configured_provider(Settings.from_env(values), repo)
    config = next(
        c
        for c in Registry.load("config/registry-hosted.example.json").snapshots()
        if c.runtime_profile.environment_type == "openai_hosted"
    )
    session = asyncio.run(provider.create_session(config, "run", initial_input="Synthetic input"))
    assert session.id == "session"
    assert session.environment.id == "env"
    assert captured[0]["environment"]["type"] == "openai_hosted"
    assert captured[0]["environment"]["plugins"][0]["name"] == "shopops-analysis"
    assert captured[0]["agent"]["multi_agent"] == {"enabled": True, "max_concurrent_subagents": 2}


def test_hosted_application_starts_without_provider_network(tmp_path):
    from fastapi.testclient import TestClient

    from app.main import create_app

    values = environment(tmp_path) | {
        "AGENT_PROVIDER": "openai_agents",
        "OPENAI_API_KEY": "synthetic",
        "OPENAI_MODEL": "gpt-6-astra",
        "CONFIG_PATH": "config/registry-hosted.example.json",
    }
    with TestClient(create_app(settings=Settings.from_env(values))) as client:
        assert client.get("/ready").status_code == 200
