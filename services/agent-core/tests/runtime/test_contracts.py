import pytest
from pydantic import ValidationError

from app.contracts.models import ConfigSnapshot


def test_legacy_profile_is_immutable_none(registry):
    snapshot = registry.snapshots()[0]
    assert snapshot.runtime_profile.profile_id == "conversation-v1"
    assert snapshot.runtime_profile.environment_type == "none"
    encoded = snapshot.model_dump()
    encoded.pop("runtime_profile")
    assert ConfigSnapshot.model_validate(encoded).runtime_profile == snapshot.runtime_profile


def test_closed_hosted_profile():
    from app.contracts.runtime import RuntimeProfile

    profile = RuntimeProfile(
        profile_id="shopops-hosted-v1",
        environment_type="openai_hosted",
        bundle_id="shopops-hosted-v1",
        bundle_version="1",
        bundle_sha256="a" * 64,
        container_size="small",
        multi_agent_enabled=True,
        max_concurrent_subagents=2,
    )
    assert profile.setup_timeout_seconds == 60
    for updates in (
        {"bundle_sha256": "bad"},
        {"network_access": "enabled"},
        {"max_concurrent_subagents": 3},
        {"environment_type": "none"},
        {"profile_id": "unknown"},
        {"max_artifact_bytes": 1048577},
    ):
        with pytest.raises(ValidationError):
            RuntimeProfile.model_validate(profile.model_dump() | updates)


def test_explicit_null_profile_normalizes_to_legacy(registry):
    data = registry.snapshots()[0].model_dump() | {"runtime_profile": None}
    assert ConfigSnapshot.model_validate(data).runtime_profile.environment_type == "none"
