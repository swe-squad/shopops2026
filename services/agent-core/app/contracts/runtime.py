"""Immutable shared hosted-runtime boundary. No provider I/O occurs here."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.contracts.identity import Scope


class RuntimeRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RuntimeProfile(RuntimeRecord):
    profile_id: Literal["conversation-v1", "shopops-hosted-v1"] = "conversation-v1"
    environment_type: Literal["none", "openai_hosted"] = "none"
    bundle_id: str | None = None
    bundle_version: str | None = None
    bundle_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    container_size: Literal["small"] | None = None
    network_access: Literal["disabled"] = "disabled"
    multi_agent_enabled: bool = False
    max_concurrent_subagents: int = 0
    setup_timeout_seconds: Literal[60] = 60
    max_artifacts: int = Field(default=2, ge=1, le=2)
    max_artifact_bytes: int = Field(default=1048576, ge=1, le=1048576)

    @model_validator(mode="after")
    def consistent(self) -> RuntimeProfile:
        bundle = (self.bundle_id, self.bundle_version, self.bundle_sha256, self.container_size)
        if self.profile_id == "conversation-v1":
            if (
                self.environment_type != "none"
                or any(v is not None for v in bundle)
                or self.multi_agent_enabled
                or self.max_concurrent_subagents != 0
            ):
                raise ValueError("Inconsistent conversation runtime")
        elif (
            self.environment_type != "openai_hosted"
            or not all(bundle)
            or self.bundle_id != "shopops-hosted-v1"
            or not self.multi_agent_enabled
            or self.max_concurrent_subagents != 2
        ):
            raise ValueError("Inconsistent hosted runtime")
        return self


class RuntimeBundle(RuntimeRecord):
    bundle_id: str
    bundle_version: str
    bundle_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    inline_plugin: dict = Field(repr=False, exclude=True)


class ProviderEnvironment(RuntimeRecord):
    id: str = Field(min_length=1)
    state: Literal["provisioning", "connected", "failed", "unavailable"]
    error: (
        Literal["environment_failed", "environment_timeout", "environment_unavailable"] | None
    ) = None


class ProviderArtifact(RuntimeRecord):
    id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    turn_id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    size: int = Field(ge=0, le=1048576)
    media_type: Literal["application/json", "text/markdown"]


class ArtifactRecord(ProviderArtifact):
    # id is the local UUID; provider_id is never exposed by the application API.
    provider_id: str = Field(min_length=1)
    scope: Scope
    conversation_id: str
    run_id: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    availability: Literal["available", "unavailable"] = "available"
