"""Closed report format shared by worker validation and bundle authors."""

from typing import Literal

from pydantic import Field

from app.contracts.models import Record, Source
from app.tools.validation import Metrics


class KnowledgeFinding(Record):
    reference: str = Field(min_length=1)
    finding: str = Field(min_length=1, max_length=2000)


class RuntimeReport(Record):
    schema_version: Literal["1"]
    metrics: Metrics
    knowledge_findings: tuple[KnowledgeFinding, ...] = Field(max_length=10)
    sources: tuple[Source, ...]
