"""Allowlisted upstream response shapes; never relay arbitrary service JSON."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


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
        "snapshot_ready",
        "failed",
        "cancelled",
        "partial",
    ]
    coverage: Coverage | None = None
    error_code: str | None = Field(default=None, pattern=r"^[A-Z0-9_]{1,64}$")
    refresh_mode: Literal["full_snapshot"] | None = None
    applied_source_revision: int | None = Field(default=None, ge=0, strict=True)

    @model_validator(mode="after")
    def snapshot_has_no_interval_coverage(self) -> "OperationStatus":
        if self.refresh_mode == "full_snapshot" and self.coverage is not None:
            raise ValueError("Snapshot refresh cannot certify historical interval coverage")
        if self.status == "snapshot_ready" and (
            self.refresh_mode != "full_snapshot" or self.applied_source_revision is None
        ):
            raise ValueError("Snapshot completion requires its mode and published revision")
        return self
