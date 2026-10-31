from collections.abc import Callable
from typing import Literal, Protocol

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
    Source,
)
from app.contracts.runtime import ArtifactRecord, ProviderEnvironment
from app.contracts.tools import PendingToolCall, ToolResult


class Repository(Protocol):
    async def save_runtime(
        self, scope: Scope, conversation_id: str, environment: ProviderEnvironment
    ) -> None: ...
    async def get_runtime(
        self, scope: Scope, conversation_id: str
    ) -> ProviderEnvironment | None: ...
    async def save_artifacts(
        self, scope: Scope, run_id: str, artifacts: tuple[ArtifactRecord, ...]
    ) -> None: ...
    async def list_artifacts(
        self, scope: Scope, run_id: str, after: str | None = None, limit: int = 50
    ) -> Page[ArtifactRecord]: ...
    async def get_saved_artifacts(
        self, scope: Scope, run_id: str
    ) -> tuple[ArtifactRecord, ...] | None: ...
    async def get_artifact(self, scope: Scope, artifact_id: str) -> ArtifactRecord: ...
    async def load_tool_results(self, session_id: str, turn_id: str) -> tuple[ToolResult, ...]: ...

    async def provision(
        self, scope: Scope, template_id: str, config_revision: str
    ) -> IdempotentResult[Orchestrator]: ...
    async def create_conversation(
        self,
        scope: Scope,
        orchestrator_id: str,
        client_conversation_id: str,
        *,
        expected_config_revision: str | None = None,
    ) -> IdempotentResult[Conversation]: ...
    async def enqueue_message(
        self,
        scope: Scope,
        conversation_id: str,
        client_message_id: str,
        content: str,
        *,
        output_mode: Literal["text", "report"] = "text",
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
    async def save_session_mapping(
        self, run_id: str, session_id: str, *, input_submitted: bool = False
    ) -> None: ...
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

    async def load_sources(self, session_id: str, turn_id: str) -> tuple[Source, ...]: ...
