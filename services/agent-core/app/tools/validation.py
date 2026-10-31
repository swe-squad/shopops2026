"""Closed v1 tool schemas. Invalid/oversized output is rejected, never truncated."""

import json
import re
from datetime import date, datetime, timedelta
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.contracts.models import ConfigSnapshot, Message
from app.contracts.tools import ToolDefinition, ToolResult

MAX_RESULT_BYTES = 32 * 1024
Limit = Annotated[int, Field(strict=True, ge=1, le=20)]


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class DateArgs(Closed):
    sku: str = Field(min_length=1, max_length=64)
    start_date: str
    end_date: str

    @field_validator("start_date", "end_date")
    @classmethod
    def iso_date(cls, value: str) -> str:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("ISO date required")
        date.fromisoformat(value)
        return value

    @model_validator(mode="after")
    def ordered(self) -> DateArgs:
        days = (date.fromisoformat(self.end_date) - date.fromisoformat(self.start_date)).days
        if not 0 <= days < 90:
            raise ValueError("inclusive date range must be 1..90 days")
        if date.fromisoformat(self.start_date).toordinal() <= days + 1:
            raise ValueError("baseline date range is not representable")
        return self


class SearchArgs(Closed):
    query: str = Field(min_length=1, max_length=1000)
    limit: Limit = 5

    @field_validator("query")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query is empty")
        return value


class HistoryArgs(Closed):
    before_sequence: Annotated[int, Field(strict=True, ge=1)] | None = None
    limit: Limit = 20


class Counts(Closed):
    start_date: str
    end_date: str
    orders: int = Field(ge=0)
    returns: int = Field(ge=0)
    return_rate: float | None

    @model_validator(mode="after")
    def calculated(self) -> Counts:
        if self.returns > self.orders:
            raise ValueError("returns exceed orders")
        expected = round(self.returns / self.orders * 100, 6) if self.orders else None
        if self.return_rate != expected:
            raise ValueError("rate differs from counts")
        return self


class Metrics(Counts):
    sku: str
    timezone: str
    baseline: Counts
    change_percentage_points: float | None

    @model_validator(mode="after")
    def change(self) -> Metrics:
        expected = (
            round(self.return_rate - self.baseline.return_rate, 6)
            if self.return_rate is not None and self.baseline.return_rate is not None
            else None
        )
        if self.change_percentage_points != expected or self.timezone != "Asia/Ho_Chi_Minh":
            raise ValueError("invalid metrics")
        return self


class Category(Closed):
    category: str = Field(min_length=1)
    count: int = Field(ge=0)
    evidence: list[str] = Field(max_length=20)


class Reviews(Closed):
    sku: str
    start_date: str
    end_date: str
    categories: list[Category] = Field(max_length=20)


class Match(Closed):
    document_id: str
    chunk_id: str
    excerpt: str = Field(min_length=1, max_length=4000)
    bundle_id: str
    version: str


class SearchResult(Closed):
    matches: list[Match] = Field(max_length=20)


class HistoryResult(Closed):
    messages: list[Message] = Field(max_length=20)


ARGUMENTS = {
    "get_return_metrics": DateArgs,
    "get_review_summary": DateArgs,
    "search_knowledge": SearchArgs,
    "get_conversation_history": HistoryArgs,
}
OUTPUTS = {
    "get_return_metrics": Metrics,
    "get_review_summary": Reviews,
    "search_knowledge": SearchResult,
    "get_conversation_history": HistoryResult,
}
PERMISSIONS = {
    "get_return_metrics": "conversation:write",
    "get_review_summary": "conversation:write",
    "search_knowledge": "conversation:write",
    "get_conversation_history": "history:read",
}


def definitions() -> tuple[ToolDefinition, ...]:
    return tuple(
        ToolDefinition(
            name=name, description=name.replace("_", " "), input_schema=cls.model_json_schema()
        )
        for name, cls in ARGUMENTS.items()
    )


def validate_arguments(name: str, arguments: dict) -> dict:
    if name not in ARGUMENTS:
        raise ValueError("unknown tool")
    return ARGUMENTS[name].model_validate(arguments).model_dump()


def validate_result(name: str, value: dict) -> ToolResult:
    if len(json.dumps(value, ensure_ascii=False, allow_nan=False).encode()) > MAX_RESULT_BYTES:
        raise ValueError("tool result exceeds 32 KiB")
    result = ToolResult.model_validate(value)
    if result.schema_version != "1":
        raise ValueError("unsupported schema version")
    if result.error:
        if result.data is not None or result.sources or result.observed_at is not None:
            raise ValueError("error must not carry data")
    else:
        if result.data is None or result.observed_at is None:
            raise ValueError("incomplete success envelope")
        observed = datetime.fromisoformat(result.observed_at.replace("Z", "+00:00"))
        if observed.tzinfo is None:
            raise ValueError("observed_at requires timezone")
        OUTPUTS[name].model_validate(result.data)
    return result


def validate_context(
    name: str, arguments: dict, result: ToolResult, conversation_id: str, config: ConfigSnapshot
) -> None:
    """Check upstream success against the trusted request, before it is persisted."""
    if result.error:
        return
    data = result.data
    if name in {"get_return_metrics", "get_review_summary"}:
        if any(data[key] != arguments[key] for key in ("sku", "start_date", "end_date")):
            raise ValueError("upstream result does not match query")
        if name == "get_return_metrics":
            start = date.fromisoformat(arguments["start_date"])
            end = date.fromisoformat(arguments["end_date"])
            baseline = data["baseline"]
            if baseline["start_date"] != str(
                start - timedelta(days=(end - start).days + 1)
            ) or baseline["end_date"] != str(start - timedelta(days=1)):
                raise ValueError("upstream baseline interval mismatch")
        if not result.sources or any(source.type != "data" for source in result.sources):
            raise ValueError("missing data evidence")
        return
    if name == "search_knowledge":
        matches = data["matches"]
        if len(matches) > arguments["limit"] or any(
            m["bundle_id"] != config.knowledge_bundle or m["version"] != config.knowledge_version
            for m in matches
        ):
            raise ValueError("upstream knowledge bundle mismatch")
        expected = {
            (
                "knowledge",
                f"knowledge:{m['bundle_id']}:{m['version']}:{m['document_id']}#{m['chunk_id']}",
            )
            for m in matches
        }
    else:
        messages = data["messages"]
        boundary = arguments["before_sequence"]
        if len(messages) > arguments["limit"] or any(
            m["conversation_id"] != conversation_id
            or (boundary is not None and m["sequence"] >= boundary)
            for m in messages
        ):
            raise ValueError("upstream history scope mismatch")
        sequences = [m["sequence"] for m in messages]
        if sequences != sorted(set(sequences)):
            raise ValueError("upstream history order mismatch")
        expected = {("history", f"history:{conversation_id}:{m['id']}") for m in messages}
    if {(s.type, s.reference) for s in result.sources} != expected:
        raise ValueError("upstream references do not match returned evidence")
