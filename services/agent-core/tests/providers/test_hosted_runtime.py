"""Request boundary regressions; the SDK transport and bundle builder are external seams."""

import asyncio
import base64
import json
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.contracts.errors import ConfigurationConflict, ProviderOutcomeUnknown
from app.contracts.runtime import RuntimeBundle, RuntimeProfile
from app.providers.hosted_runtime import build_hosted_environment
from app.providers.openai_agents import OpenAIAgentsProvider


def hosted_profile():
    return RuntimeProfile(
        profile_id="shopops-hosted-v1",
        environment_type="openai_hosted",
        bundle_id="shopops-hosted-v1",
        bundle_version="1",
        bundle_sha256="a" * 64,
        container_size="small",
        multi_agent_enabled=True,
        max_concurrent_subagents=2,
    )


def approved_bundle():
    # T07 validates actual ZIP entries and the aggregate digest. This double models its output.
    return RuntimeBundle(
        bundle_id="shopops-hosted-v1",
        bundle_version="1",
        bundle_sha256="a" * 64,
        inline_plugin={
            "type": "inline",
            "name": "shopops-analysis",
            "description": "Approved ShopOps analysis skills",
            "source": {
                "type": "base64",
                "media_type": "application/zip",
                "data": base64.b64encode(b"synthetic registered ZIP").decode(),
            },
        },
    )


def test_environment_uses_only_approved_sdk_fields():
    bundle = approved_bundle()
    result = build_hosted_environment(hosted_profile(), bundle)
    assert result == {
        "type": "openai_hosted",
        "container_size": "small",
        "network": {"access": "disabled"},
        "plugins": [bundle.inline_plugin],
    }
    # No alias to the mutable private dictionary survives validation.
    result["plugins"][0]["name"] = "changed"
    assert bundle.inline_plugin["name"] == "shopops-analysis"


@pytest.mark.parametrize(
    "change",
    [
        {"bundle_id": "other"},
        {"bundle_version": "2"},
        {"bundle_sha256": "b" * 64},
    ],
)
def test_environment_rejects_mismatched_bundle(change):
    with pytest.raises(ConfigurationConflict):
        build_hosted_environment(hosted_profile(), approved_bundle().model_copy(update=change))


@pytest.mark.parametrize(
    "change",
    [
        {"network_access": "enabled"},
        {"container_size": "large"},
        {"max_concurrent_subagents": 3},
        {"environment_type": "none"},
    ],
)
def test_environment_revalidates_profile_before_io(change):
    with pytest.raises(ConfigurationConflict):
        build_hosted_environment(hosted_profile().model_copy(update=change), approved_bundle())


@pytest.mark.parametrize("field", ["env", "packages", "setup_commands", "mcp_servers"])
def test_plugin_rejects_unexpected_fields(field):
    bundle = approved_bundle()
    plugin = deepcopy(bundle.inline_plugin)
    plugin[field] = {"secret": "synthetic-secret"}
    with pytest.raises(ConfigurationConflict):
        build_hosted_environment(
            hosted_profile(), bundle.model_copy(update={"inline_plugin": plugin})
        )


@pytest.mark.parametrize(
    "source",
    [
        {"type": "url", "url": "https://invalid.example/plugin.zip"},
        {"type": "base64", "media_type": "application/zip", "data": "!!!"},
        {"type": "base64", "media_type": "application/zip", "data": ""},
    ],
)
def test_plugin_requires_inline_zip_source(source):
    bundle = approved_bundle()
    plugin = dict(bundle.inline_plugin, source=source)
    with pytest.raises(ConfigurationConflict):
        build_hosted_environment(
            hosted_profile(), bundle.model_copy(update={"inline_plugin": plugin})
        )


def test_hosted_create_pins_request_and_excludes_backend_secrets(config, monkeypatch):
    import app.agents.runtime_bundle as bundles

    monkeypatch.setattr(bundles, "build_runtime_bundle", lambda profile: approved_bundle())
    for name in ("OPENAI_API_KEY", "MCP_TOKEN_SIGNING_KEY", "AUTH_JWT_SECRET"):
        monkeypatch.setenv(name, "synthetic-backend-secret")

    async def exercise():
        sessions = SimpleNamespace(
            create=AsyncMock(
                return_value={
                    "id": "session",
                    "environment": {"type": "openai_hosted", "id": "env"},
                }
            )
        )
        client = SimpleNamespace(beta=SimpleNamespace(agents=SimpleNamespace(sessions=sessions)))
        provider = OpenAIAgentsProvider(client)
        result = await provider.create_session(
            config.model_copy(update={"runtime_profile": hosted_profile()}),
            "run-1",
            initial_input="synthetic input",
        )
        assert result.id == "session" and result.input_submitted
        assert result.environment.id == "env"
        assert result.environment.state == "provisioning"
        request = sessions.create.call_args.kwargs
        assert request["input"] == "synthetic input"
        assert request["metadata"] == {"initial_run_id": "run-1"}
        assert request["environment"]["type"] == "openai_hosted"
        assert request["agent"]["multi_agent"] == {"enabled": True, "max_concurrent_subagents": 2}
        assert "synthetic-backend-secret" not in json.dumps(request, default=str)
        assert "localhost" not in json.dumps(request, default=str)
        assert sessions.create.call_count == 1

    asyncio.run(exercise())


def test_bundle_failure_never_creates_or_falls_back(config, monkeypatch):
    import app.agents.runtime_bundle as bundles

    monkeypatch.setattr(
        bundles,
        "build_runtime_bundle",
        lambda profile: approved_bundle().model_copy(update={"bundle_version": "wrong"}),
    )

    async def exercise():
        sessions = SimpleNamespace(create=AsyncMock())
        client = SimpleNamespace(beta=SimpleNamespace(agents=SimpleNamespace(sessions=sessions)))
        provider = OpenAIAgentsProvider(client)
        with pytest.raises(ConfigurationConflict):
            await provider.create_session(
                config.model_copy(update={"runtime_profile": hosted_profile()}),
                "run",
                initial_input="synthetic input",
            )
        assert sessions.create.call_count == 0

    asyncio.run(exercise())


def test_unknown_create_has_no_retry_or_fallback(config, monkeypatch):
    import app.agents.runtime_bundle as bundles

    monkeypatch.setattr(bundles, "build_runtime_bundle", lambda profile: approved_bundle())

    async def exercise():
        sessions = SimpleNamespace(create=AsyncMock(side_effect=TimeoutError("sensitive detail")))
        provider = OpenAIAgentsProvider(
            SimpleNamespace(beta=SimpleNamespace(agents=SimpleNamespace(sessions=sessions)))
        )
        with pytest.raises(ProviderOutcomeUnknown, match="^provider_outcome_unknown$"):
            await provider.create_session(
                config.model_copy(update={"runtime_profile": hosted_profile()}),
                "run",
                initial_input="synthetic input",
            )
        assert sessions.create.call_count == 1

    asyncio.run(exercise())


def test_invalid_pinned_profile_cannot_silently_select_none(config):
    async def exercise():
        sessions = SimpleNamespace(create=AsyncMock())
        provider = OpenAIAgentsProvider(
            SimpleNamespace(beta=SimpleNamespace(agents=SimpleNamespace(sessions=sessions)))
        )
        invalid = hosted_profile().model_copy(update={"environment_type": "none"})
        with pytest.raises(ConfigurationConflict):
            await provider.create_session(
                config.model_copy(update={"runtime_profile": invalid}), "run", initial_input="input"
            )
        assert sessions.create.call_count == 0

    asyncio.run(exercise())
