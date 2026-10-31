from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager
from typing import Literal, Protocol

from app.contracts.models import ApplicationResponse, ConfigSnapshot, Record
from app.contracts.tools import PendingToolCall, ToolResult


class ProviderSession(Record):
    id: str


class ProviderItem(Record):
    id: str
    turn_id: str
    response: ApplicationResponse


class ProviderSnapshot(Record):
    session_id: str
    root_turn_id: str | None = None
    root_status: Literal[
        "idle", "running", "waiting_tool", "completed", "failed", "cancelled", "unknown"
    ]
    input_run_id: str | None = None
    pending_calls: tuple[PendingToolCall, ...] = ()
    response: ApplicationResponse | None = None
    item_id: str | None = None


class ProviderEvent(Record):
    id: str
    session_id: str
    turn_id: str
    kind: Literal["status", "tool_pending", "completed", "failed", "cancelled"]
    is_root: bool = True


class ProviderEventStream(Protocol):
    async def wait_ready(self) -> None: ...
    def __aiter__(self) -> AsyncIterator[ProviderEvent]: ...


class AgentProvider(Protocol):
    async def create_session(
        self, config: ConfigSnapshot, correlation_id: str
    ) -> ProviderSession: ...
    async def inspect_session(self, session_id: str) -> ProviderSnapshot: ...
    async def submit_input(self, session_id: str, content: str, run_id: str) -> str: ...
    def stream_events(
        self, session_id: str
    ) -> AbstractAsyncContextManager[ProviderEventStream]: ...
    async def submit_tool_result(self, call: PendingToolCall, result: ToolResult) -> None: ...
    async def list_items(self, session_id: str) -> tuple[ProviderItem, ...]: ...
    async def cancel_turn(self, session_id: str, turn_id: str) -> None: ...
    async def delete_session(self, session_id: str) -> None: ...
