from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.contracts.models import ApplicationResponse, RunState

Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProvisionInput(Input):
    template_id: Identifier
    config_revision: Identifier


class ConversationInput(Input):
    orchestrator_id: Identifier
    client_conversation_id: Identifier


class MessageInput(Input):
    client_message_id: Identifier
    content: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8000)]


class ProvisionOutput(BaseModel):
    orchestrator_id: str
    config_revision: str


class ConversationOutput(BaseModel):
    conversation_id: str


class EnqueueOutput(BaseModel):
    message_id: str
    run_id: str
    polling_url: str


class RunOutput(BaseModel):
    run_id: str
    status: RunState
    response: ApplicationResponse | None = None
    error: str | None = None


class MessageOutput(BaseModel):
    id: str
    conversation_id: str
    run_id: str
    role: str
    content: str
    sequence: int
    created_at: datetime


class EventOutput(BaseModel):
    id: str
    run_id: str
    sequence: int
    type: str
    tool_name: str | None = None
    error: str | None = None
    created_at: datetime


class HistoryOutput(BaseModel):
    items: list[MessageOutput]
    next_cursor: str | None = None


class EventsOutput(BaseModel):
    items: list[EventOutput]
    next_cursor: str | None = None


class HealthOutput(BaseModel):
    status: str = Field()
