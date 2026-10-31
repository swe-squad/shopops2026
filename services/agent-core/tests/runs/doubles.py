from contextlib import asynccontextmanager

from app.contracts.models import ApplicationResponse, Source
from app.contracts.provider import ProviderSession, ProviderSnapshot
from app.contracts.tools import PendingToolCall, ToolDefinition, ToolResult


class Clock:
    def __init__(self, value):
        self.value = value

    def __call__(self):
        return self.value


class Stream:
    def __init__(self, provider):
        self.provider = provider

    async def wait_ready(self):
        self.provider.ready = True

    def __aiter__(self):
        return self.events()

    async def events(self):
        for event in self.provider.events:
            yield event


class ControlledProvider:
    """Test-only boundary double: deliberately closes its stream before completion."""

    def __init__(self, mode="answer"):
        self.mode = mode
        self.submissions = []
        self.creations = 0
        self.results = []
        self.ready = False
        self.events = []
        self.snapshot = ProviderSnapshot(session_id="session-a", root_status="idle")
        self.cancel_confirmed = True
        self.cancel_requested = False
        self.delete_fails = False

    async def create_session(self, config, correlation_id):
        self.creations += 1
        return ProviderSession(id="session-a")

    async def inspect_session(self, session_id):
        return self.snapshot

    @asynccontextmanager
    async def stream_events(self, session_id):
        yield Stream(self)
        self.ready = False

    async def submit_input(self, session_id, content, run_id):
        assert self.ready, "stream must be ready before submission"
        self.submissions.append(run_id)
        if self.mode == "unknown":
            self.snapshot = ProviderSnapshot(session_id=session_id, root_status="unknown")
            raise TimeoutError("private transport details must never be persisted")
        status = "waiting_tool" if self.mode == "tool" else "completed"
        if self.mode == "active":
            status = "running"
        self.snapshot = ProviderSnapshot(
            session_id=session_id,
            root_turn_id="turn-a",
            root_status=status,
            input_run_id=run_id,
            item_id="item-a",
            response=ApplicationResponse(kind="answer", text="Đã xử lý.")
            if status == "completed"
            else None,
            pending_calls=(
                PendingToolCall(
                    session_id=session_id,
                    turn_id="turn-a",
                    call_id="call-a",
                    name="search_knowledge",
                    arguments={"query": "policy"},
                ),
            )
            if status == "waiting_tool"
            else (),
        )
        return "turn-a"

    async def submit_tool_result(self, call, result):
        self.results.append(result)
        self.snapshot = self.snapshot.model_copy(
            update={
                "root_status": "completed",
                "pending_calls": (),
                "item_id": "item-a",
                "response": ApplicationResponse(
                    kind="answer",
                    text="Chính sách xử lý.",
                    sources=(Source(type="knowledge", reference="kb:v1:policy"),),
                ),
            }
        )

    async def cancel_turn(self, session_id, turn_id):
        self.cancel_requested = True
        if self.cancel_confirmed:
            self.snapshot = self.snapshot.model_copy(update={"root_status": "cancelled"})

    async def list_items(self, session_id):
        return ()

    async def delete_session(self, session_id):
        if self.delete_fails:
            raise TimeoutError("provider deletion failed")


class ControlledBridge:
    def __init__(self):
        self.executions = 0

    def definitions(self, config):
        return (ToolDefinition(name="search_knowledge", description="Search", input_schema={}),)

    async def execute(self, scope, conversation_id, config, call):
        self.executions += 1
        return ToolResult(
            data={"excerpt": "policy"},
            sources=(Source(type="knowledge", reference="kb:v1:policy"),),
        )
