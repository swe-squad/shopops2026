from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, Field

from app.source.entities import Record


class Pagination(BaseModel):
    limit: int
    offset: int
    total: int


class Page[T](BaseModel):
    data: list[T]
    pagination: Pagination
    applied_source_revision: int


class Result[T](BaseModel):
    data: T
    applied_source_revision: int


class SourcePage[T](BaseModel):
    data: list[T]
    pagination: Pagination
    source_revision: int


class SourceResult[T](BaseModel):
    data: T
    source_revision: int


class Mutation[T](BaseModel):
    data: T | None
    source_revision: int | None
    mutation_status: Literal["pending", "applied", "unknown", "rejected"]
    run_id: UUID
    sync_status: str
    status_url: str


class Empty(Record):
    pass


class SettingsPatch(Record):
    as_of: AwareDatetime | None = None
    recent_days: int | None = Field(default=None, gt=0)
    baseline_days: int | None = Field(default=None, gt=0)


class MartSettings(Record):
    as_of: AwareDatetime
    recent_days: int = Field(gt=0)
    baseline_days: int = Field(gt=0)
