from collections.abc import Callable
from typing import Protocol

from app.contracts.identity import Scope
from app.contracts.models import (
    ApplicationResponse,
    ConfigSnapshot,
    Conversation,
    EnqueueResult,
    IdempotentResult,
    Message,
    Orchestrator,
    Page,
    Run,
    RunEvent,
    RunState,
)
from app.contracts.tools import PendingToolCall, ToolResult


class Repository(Protocol):
    async def provision(
        self, scope: Scope, template_id: str, config_revision: str
    ) -> IdempotentResult[Orchestrator]: ...
    async def create_conversation(
        self, scope: Scope, orchestrator_id: str, client_conversation_id: str
    ) -> IdempotentResult[Conversation]: ...
    async def enqueue_message(
        self, scope: Scope, conversation_id: str, client_message_id: str, content: str
    ) -> EnqueueResult: ...
    async def get_conversation(self, scope: Scope, conversation_id: str) -> Conversation: ...
    async def get_run(self, scope: Scope, run_id: str) -> Run: ...
    async def get_history(
        self, scope: Scope, conversation_id: str, after: str | None = None, limit: int = 50
    ) -> Page[Message]: ...
    async def get_events(
        self, scope: Scope, run_id: str, after: str | None = None, limit: int = 50
    ) -> Page[RunEvent]: ...
    async def get_config_snapshot(self, scope: Scope, conversation_id: str) -> ConfigSnapshot: ...
    async def claim_next_run(self) -> Run | None: ...
    async def recover_interrupted(self) -> None: ...
    async def pending_runs(self) -> tuple[Run, ...]: ...
    async def execution_context(self, run_id: str) -> tuple[Conversation, Message]: ...
    async def save_session_mapping(self, run_id: str, session_id: str) -> None: ...
    async def mark_submission(
        self, run_id: str, marker: str, turn_id: str | None = None
    ) -> None: ...
    async def transition_run(
        self,
        run_id: str,
        expected: tuple[RunState, ...],
        target: RunState,
        *,
        error: str | None = None,
        block: bool = False,
    ) -> bool: ...
    async def append_event(
        self,
        run_id: str,
        event_type: str,
        *,
        provider_event_id: str | None = None,
        tool_name: str | None = None,
        error: str | None = None,
    ) -> None: ...
    async def get_tool_result(
        self, run_id: str, call: PendingToolCall
    ) -> tuple[ToolResult, bool] | None: ...
    async def begin_tool_call(self, run_id: str, call: PendingToolCall, maximum: int) -> bool: ...
    async def record_tool_result(
        self, run_id: str, call: PendingToolCall, result: ToolResult
    ) -> ToolResult: ...
    async def mark_tool_delivered(self, run_id: str, call: PendingToolCall) -> None: ...
    async def complete_run(
        self, run_id: str, turn_id: str, item_id: str, response: ApplicationResponse
    ) -> None: ...
    async def activate_revision(self, scope: Scope, template_id: str, revision: str) -> None: ...
    async def delete_conversation(
        self, scope: Scope, conversation_id: str, delete_session: Callable
    ) -> None: ...
    async def prune(self, before: str) -> tuple[int, int]: ...
