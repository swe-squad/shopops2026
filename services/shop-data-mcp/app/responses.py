"""Allowlisted upstream response shapes; never relay arbitrary service JSON."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class StrictResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ApprovalCreated(StrictResponse):
    request_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")
    status: Literal["pending", "denied"]


class Coverage(StrictResponse):
    dataset_ids: list[Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,62}$")]] = Field(
        max_length=100
    )
    start: AwareDatetime
    end: AwareDatetime
    collection_completed_at: AwareDatetime | None = None
    processing_completed_at: AwareDatetime | None = None


class OperationStatus(StrictResponse):
    operation_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")
    subject: str
    shop_key: str
    status: Literal[
        "queued",
        "collecting",
        "raw_available",
        "processing",
        "mart_ready",
        "failed",
        "cancelled",
        "partial",
    ]
    coverage: Coverage | None = None
    error_code: str | None = Field(default=None, pattern=r"^[A-Z0-9_]{1,64}$")
