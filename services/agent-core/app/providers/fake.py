"""Deterministic synthetic provider. Tools always cross the pending-call boundary."""

import asyncio
import json
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from uuid import uuid4

from app.contracts.errors import IdempotencyConflict, InvalidTransition, NotFound
from app.contracts.models import ApplicationResponse, ConfigSnapshot
from app.contracts.provider import ProviderEvent, ProviderItem, ProviderSession, ProviderSnapshot
from app.contracts.tools import PendingToolCall, ToolResult


@dataclass(frozen=True)
class Scenario:
    tool_name: str | None = None
    arguments: dict = field(default_factory=dict)
    response: ApplicationResponse | None = None
    interrupted: bool = False
    duplicate_event: bool = False


@dataclass
class _Session:
    config: ConfigSnapshot
    snapshot: ProviderSnapshot
    items: list[ProviderItem] = field(default_factory=list)
    queues: list[asyncio.Queue] = field(default_factory=list)
    deliveries: dict = field(default_factory=dict)
    turn_count: int = 0


class _Stream:
    def __init__(self, queue: asyncio.Queue) -> None:
        self.queue = queue

    async def wait_ready(self) -> None:
        pass  # Subscription queue is installed before context entry returns.

    def __aiter__(self) -> AsyncIterator[ProviderEvent]:
        return self._events()

    async def _events(self) -> AsyncIterator[ProviderEvent]:
        while (event := await self.queue.get()) is not None:
            yield event


class FakeProvider:
    def __init__(self, scenarios: Sequence[Scenario] = ()) -> None:
        self.scenarios = tuple(scenarios)
        self.sessions: dict[str, _Session] = {}

    def _session(self, session_id: str) -> _Session:
        try:
            return self.sessions[session_id]
        except KeyError:
            raise NotFound() from None

    async def create_session(
        self, config: ConfigSnapshot, correlation_id: str, *, initial_input: str | None = None
    ) -> ProviderSession:
        session_id = str(uuid4())
        self.sessions[session_id] = _Session(
            config, ProviderSnapshot(session_id=session_id, root_status="idle")
        )
        if initial_input is not None:
            await self.submit_input(session_id, initial_input, correlation_id)
        return ProviderSession(id=session_id, input_submitted=initial_input is not None)

    async def inspect_session(self, session_id: str) -> ProviderSnapshot:
        return self._session(session_id).snapshot

    def _emit(self, session: _Session, kind: str, duplicate: bool = False) -> None:
        event = ProviderEvent(
            id=str(uuid4()),
            session_id=session.snapshot.session_id,
            turn_id=session.snapshot.root_turn_id,
            kind=kind,
        )
        for queue in session.queues:
            queue.put_nowait(event)
            if duplicate:
                queue.put_nowait(event)

    def _finish(self, session: _Session, response: ApplicationResponse) -> None:
        item = ProviderItem(
            id=str(uuid4()), turn_id=session.snapshot.root_turn_id, response=response
        )
        session.items.append(item)
        session.snapshot = session.snapshot.model_copy(
            update={
                "root_status": "completed",
                "pending_calls": (),
                "response": response,
                "item_id": item.id,
            }
        )
        self._emit(session, "completed")

    async def submit_input(self, session_id: str, content: str, run_id: str) -> str:
        session = self._session(session_id)
        if session.snapshot.root_status not in {"idle", "completed", "failed", "cancelled"}:
            raise InvalidTransition()
        scenario = (
            self.scenarios[session.turn_count]
            if session.turn_count < len(self.scenarios)
            else Scenario()
        )
        session.turn_count += 1
        turn = str(uuid4())
        session.snapshot = ProviderSnapshot(
            session_id=session_id, root_turn_id=turn, root_status="running", input_run_id=run_id
        )
        self._emit(session, "status", scenario.duplicate_event)
        if scenario.interrupted:
            for queue in session.queues:
                queue.put_nowait(None)
        elif scenario.tool_name:
            if scenario.tool_name not in session.config.capabilities:
                raise InvalidTransition()
            call = PendingToolCall(
                session_id=session_id,
                turn_id=turn,
                call_id=str(uuid4()),
                name=scenario.tool_name,
                arguments=scenario.arguments,
            )
            session.snapshot = session.snapshot.model_copy(
                update={"root_status": "waiting_tool", "pending_calls": (call,)}
            )
            self._emit(session, "tool_pending")
        else:
            self._finish(
                session,
                scenario.response
                or ApplicationResponse(
                    kind="clarification", text="Bạn cho biết SKU và khoảng ngày cần xem?"
                ),
            )
        return turn

    @asynccontextmanager
    async def stream_events(self, session_id: str) -> AsyncIterator[_Stream]:
        session = self._session(session_id)
        queue = asyncio.Queue()
        session.queues.append(queue)
        try:
            yield _Stream(queue)
        finally:
            session.queues.remove(queue)

    async def submit_tool_result(self, call: PendingToolCall, result: ToolResult) -> None:
        session = self._session(call.session_id)
        key = (call.turn_id, call.call_id)
        previous = session.deliveries.get(key)
        if previous is not None:
            if previous != (call, result):
                raise IdempotencyConflict()
            return
        if call not in session.snapshot.pending_calls:
            raise InvalidTransition()
        session.deliveries[key] = (call, result)
        if result.error:
            response = ApplicationResponse(
                kind="cannot_answer", text="Không thể lấy dữ liệu từ công cụ. Vui lòng thử lại sau."
            )
        else:
            summary = (result.data or {}).get("summary")
            if not summary and result.data:
                summary = "Dữ liệu công cụ (mô phỏng): " + json.dumps(
                    result.data, ensure_ascii=False, sort_keys=True
                )
            response = ApplicationResponse(
                kind="answer" if summary else "cannot_answer",
                text=summary or "Công cụ chưa cung cấp nội dung có thể trả lời.",
                sources=result.sources,
            )
        self._finish(session, response)

    async def list_items(self, session_id: str) -> tuple[ProviderItem, ...]:
        return tuple(self._session(session_id).items)

    async def cancel_turn(self, session_id: str, turn_id: str) -> None:
        session = self._session(session_id)
        if session.snapshot.root_turn_id != turn_id:
            raise InvalidTransition()
        if session.snapshot.root_status in {"completed", "failed", "cancelled"}:
            return
        session.snapshot = session.snapshot.model_copy(
            update={"root_status": "cancelled", "pending_calls": ()}
        )
        self._emit(session, "cancelled")

    async def delete_session(self, session_id: str) -> None:
        session = self.sessions.pop(session_id, None)
        if session:
            for queue in session.queues:
                queue.put_nowait(None)
