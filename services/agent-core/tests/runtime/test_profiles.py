import pytest

from app.contracts.errors import ConfigurationConflict


def test_revision_cannot_change_runtime(registry):
    from app.contracts.runtime import RuntimeProfile

    original = registry.snapshots()[0]
    hosted = RuntimeProfile(
        profile_id="shopops-hosted-v1",
        environment_type="openai_hosted",
        bundle_id="shopops-hosted-v1",
        bundle_version="1",
        bundle_sha256="a" * 64,
        container_size="small",
        multi_agent_enabled=True,
        max_concurrent_subagents=2,
    )
    with pytest.raises(ConfigurationConflict):
        registry.register(original.model_copy(update={"runtime_profile": hosted}))
