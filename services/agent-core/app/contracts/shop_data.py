"""Public immutable reference; contains no phone identity."""

from pydantic import BaseModel, ConfigDict, Field


class BindingReference(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    version: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    digest: str = Field(pattern=r"^[a-f0-9]{64}$")
