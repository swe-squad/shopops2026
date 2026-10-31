from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter


class MessageInput(BaseModel):
    text: str = Field(min_length=1, max_length=2000, pattern=r"[\s\S]*\S[\s\S]*")


class Message(BaseModel):
    id: int
    text: str
    role: Literal["user", "assistant"]
    created_at: str


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
