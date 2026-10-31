from typing import Literal, Protocol

from app.contracts.identity import Scope
from app.contracts.models import ConfigSnapshot, Record, Source


class ToolDefinition(Record):
    name: str
    description: str
    input_schema: dict
    read_only: bool = True


class PendingToolCall(Record):
    session_id: str
    turn_id: str
    call_id: str
    name: str
    arguments: dict


class ToolResult(Record):
    schema_version: str = "1"
    data: dict | None = None
    sources: tuple[Source, ...] = ()
    observed_at: str | None = None
    error: (
        Literal[
            "invalid_input", "not_found", "permission_denied", "upstream_unavailable", "timeout"
        ]
        | None
    ) = None


class ToolBridge(Protocol):
    def definitions(self, config: ConfigSnapshot) -> tuple[ToolDefinition, ...]: ...

    async def execute(
        self, scope: Scope, conversation_id: str, config: ConfigSnapshot, call: PendingToolCall
    ) -> ToolResult: ...
