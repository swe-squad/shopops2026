from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


class MessageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    output_mode: Literal["text", "report"] = "text"
    client_message_id: str | None = Field(
        default=None, min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$"
    )
    text: str = Field(min_length=1, max_length=2000, pattern=r"[\s\S]*\S[\s\S]*")


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["data", "knowledge", "history"]
    reference: str = Field(min_length=1, max_length=2000)


class Artifact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    filename: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$")
    media_type: Literal["text/markdown", "application/json"]
    size: int = Field(ge=0, le=1048576, strict=True)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    availability: Literal["available", "expired", "unavailable"]


class Message(BaseModel):
    id: int | str
    text: str
    role: Literal["user", "assistant"]
    created_at: str
    kind: Literal["answer", "clarification", "cannot_answer"] | None = None
    sources: list[Source] | None = None
    artifacts: list[Artifact] | None = Field(default=None, max_length=2)


class ErrorDetail(BaseModel):
    detail: str


class DeltaEvent(BaseModel):
    type: Literal["delta"]
    text: str


class DoneEvent(BaseModel):
    type: Literal["done"]
    message: Message


class ErrorEvent(BaseModel):
    type: Literal["error"]
    message: str


ChatEvent = Annotated[DeltaEvent | DoneEvent | ErrorEvent, Field(discriminator="type")]
EVENT_ADAPTER = TypeAdapter(ChatEvent)
AUTH_RESPONSES = {401: {"model": ErrorDetail, "description": "Missing or invalid workspace token."}}
STREAM_RESPONSES = {
    **AUTH_RESPONSES,
    200: {
        "description": (
            "Server-sent events. Each data frame contains one JSON event matching the schema. "
            "Deltas are provisional; done contains the persisted authoritative reply. "
            "Errors after streaming begins use an error event, not a new HTTP status."
        ),
        "content": {
            "text/event-stream": {
                "schema": {
                    "oneOf": [
                        {"$ref": f"#/components/schemas/{event.__name__}"}
                        for event in (DeltaEvent, DoneEvent, ErrorEvent)
                    ],
                    "discriminator": {"propertyName": "type"},
                },
                "example": 'data: {"type":"delta","text":"Hello"}\n\n',
            }
        },
    },
    409: {
        "model": ErrorDetail,
        "description": "An active or uncertain previous turn blocks input.",
    },
    502: {
        "model": ErrorDetail,
        "description": "Saved provider state could not be inspected safely.",
    },
}
