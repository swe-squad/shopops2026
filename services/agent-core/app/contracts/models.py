from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.contracts.identity import Scope
from app.contracts.runtime import RuntimeProfile

RunState = Literal[
    "queued", "running", "waiting_tool", "reconciling", "completed", "failed", "cancelled"
]
TERMINAL = frozenset({"completed", "failed", "cancelled"})


class Record(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ConfigSnapshot(Record):
    runtime_profile: RuntimeProfile = Field(default_factory=RuntimeProfile)
    revision: str
    template_id: str
    model: str
    knowledge_bundle: str
    knowledge_version: str
    mcp_profile: str
    data_mcp_url: str
    knowledge_mcp_url: str
    capabilities: tuple[str, ...]

    @field_validator("capabilities")
    @classmethod
    def unique(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("duplicate capabilities")
        return values


class Orchestrator(Record):
    id: str
    tenant_id: str
    shop_id: str
    config_revision: str
    template_id: str


class Conversation(Record):
    id: str
    scope: Scope
    orchestrator_id: str
    config: ConfigSnapshot
    client_conversation_id: str
    provider_session_id: str | None = None
    status: Literal["active", "blocked", "deleting", "cleanup_failed"] = "active"
    created_at: datetime


class Source(Record):
    type: Literal["data", "knowledge", "history"]
    reference: str = Field(min_length=1)


class ApplicationResponse(Record):
    kind: Literal["answer", "clarification", "cannot_answer"]
    text: str = Field(min_length=1, max_length=32000)
    sources: tuple[Source, ...] = ()


class Message(Record):
    id: str
    conversation_id: str
    run_id: str
    role: Literal["user", "assistant"]
    content: str
    sequence: int
    provider_item_id: str | None = None
    created_at: datetime


class MessageReceipt(Record):
    id: str
    sequence: int
    created_at: datetime


class Run(Record):
    output_mode: Literal["text", "report"] = "text"
    id: str
    conversation_id: str
    client_message_id: str
    request_hash: str
    scope: Scope | None = None
    message_receipt: MessageReceipt | None = None
    state: RunState
    submission_marker: Literal["none", "session_creating", "submitting", "submitted"] = "none"
    provider_turn_id: str | None = None
    deadline: datetime
    recovery_deadline: datetime
    config: ConfigSnapshot
    response: ApplicationResponse | None = None
    error: str | None = None
    created_at: datetime


class RunEvent(Record):
    id: str
    run_id: str
    sequence: int
    type: str
    tool_name: str | None = None
    error: str | None = None
    provider_event_id: str | None = None
    created_at: datetime


class Page[T](Record):
    items: tuple[T, ...]
    next_cursor: str | None = None


class IdempotentResult[T](Record):
    record: T
    created: bool


class EnqueueResult(Record):
    message: Message
    run: Run
    created: bool
