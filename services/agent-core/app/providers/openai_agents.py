"""Official Agents API boundary: initial input is submitted atomically with creation."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from app.contracts.errors import (
    ConfigurationConflict,
    IdempotencyConflict,
    InvalidTransition,
    ProviderRequestRejected,
)
from app.contracts.errors import ProviderOutcomeUnknown as Unknown
from app.contracts.models import ApplicationResponse, ConfigSnapshot, Source
from app.contracts.provider import ProviderEvent, ProviderItem, ProviderSession, ProviderSnapshot
from app.contracts.tools import PendingToolCall, ToolResult
from app.providers.normalization import normalize_response

SourceLoader = Callable[[str, str], Awaitable[tuple[Source, ...]]]


def _dict(value: Any) -> dict:
    return value if isinstance(value, dict) else value.model_dump()


class _Events:
    def __init__(self, raw: Any, session_id: str) -> None:
        self.raw = raw
        self.session_id = session_id

    async def wait_ready(self) -> None:
        pass  # SDK stream context entry has already established the HTTP subscription.

    def __aiter__(self) -> AsyncIterator[ProviderEvent]:
        return self._iterate()

    async def _iterate(self) -> AsyncIterator[ProviderEvent]:
        try:
            async for raw in self.raw:
                event = _dict(raw)
                if event.get("session_id", event.get("session", {}).get("id")) != self.session_id:
                    raise Unknown()
                kind = {
                    "agent.session.turn.completed": "completed",
                    "agent.session.turn.failed": "failed",
                    "agent.session.turn.cancelled": "cancelled",
                    "agent.session.turn.created": "status",
                    "agent.session.turn.in_progress": "status",
                    "agent.session.requires_action": "tool_pending",
                }.get(event.get("type"))
                if event.get("type") in {
                    "error",
                    "agent.session.failed",
                    "agent.session.environment.failed",
                }:
                    raise Unknown()
                if kind == "tool_pending":
                    turns = dict.fromkeys(
                        action["turn_id"]
                        for action in event["session"].get("required_actions", [])
                        if action.get("type") == "function_call"
                    )
                    for pending_turn in turns:
                        yield ProviderEvent(
                            id=f"{event['event_id']}:{pending_turn}",
                            session_id=self.session_id,
                            turn_id=pending_turn,
                            kind="tool_pending",
                            is_root=False,
                        )
                    continue
                turn_id = event.get("turn_id")
                if kind and turn_id:
                    turn = event.get("turn", {})
                    # Missing subagent identity is not proof of root ownership.
                    is_root = "subagent_id" in turn and turn["subagent_id"] is None
                    yield ProviderEvent(
                        id=event["event_id"],
                        session_id=self.session_id,
                        turn_id=turn_id,
                        kind=kind,
                        is_root=is_root,
                    )
        except Exception:
            raise Unknown() from None
        # EOF carries no terminal meaning. The worker must inspect the session.


class OpenAIAgentsProvider:
    def __init__(self, client: Any, source_loader: SourceLoader | None = None) -> None:
        if hasattr(client, "with_options"):
            client = client.with_options(max_retries=0)
        self.client = client
        self.created_sessions: list[str] = []
        self.last_http_status: int | None = None
        self.last_error_fields: dict[str, str] = {}
        self.sessions = client.beta.agents.sessions
        self.deliveries: dict[tuple[str, str, str], tuple[PendingToolCall, ToolResult]] = {}
        self.source_loader = source_loader
        # Optimization only. Restart loses correlation, and recovery then blocks safely.
        self.correlations: dict[tuple[str, str], str] = {}

    async def create_session(
        self, config: ConfigSnapshot, correlation_id: str, *, initial_input: str | None = None
    ) -> ProviderSession:
        if initial_input is None or not initial_input.strip():
            raise ConfigurationConflict()
        from app.agents.capabilities import select_tools
        from app.agents.instructions import build_instructions
        from app.tools.validation import definitions

        tools = select_tools(config, definitions())
        try:
            session = _dict(
                await self.sessions.create(
                    agent={
                        "model": config.model,
                        "instructions": build_instructions(config),
                        "tools": [
                            {
                                "type": "function",
                                "name": t.name,
                                "description": t.description,
                                "parameters": t.input_schema,
                            }
                            for t in tools
                        ],
                    },
                    environment={"type": "none"},
                    input=initial_input,
                    metadata={"initial_run_id": correlation_id},
                    output_type=ApplicationResponse,
                )
            )
            self.created_sessions.append(session["id"])
            return ProviderSession(id=session["id"], input_submitted=True)
        except Exception as error:
            status = getattr(error, "status_code", None)
            if status in {400, 401, 403, 404, 422}:
                self.last_http_status = status
                body = getattr(error, "body", None)
                if isinstance(body, dict):
                    for name in ("code", "param"):
                        value = body.get(name)
                        if isinstance(value, str) and len(value) <= 128:
                            self.last_error_fields[name] = value
                raise ProviderRequestRejected() from None
            raise Unknown() from None

    async def aclose(self) -> None:
        if hasattr(self.client, "close"):
            await self.client.close()

    async def _roots(self, session_id: str) -> list[dict]:
        roots = []
        async for raw in self.sessions.turns.list(session_id, order="desc", limit=100):
            turn = _dict(raw)
            if "subagent_id" in turn and turn["subagent_id"] is None:
                roots.append(turn)
        return roots

    async def inspect_session(self, session_id: str) -> ProviderSnapshot:
        return await self._snapshot(session_id, include_response=True)

    async def _snapshot(self, session_id: str, *, include_response: bool) -> ProviderSnapshot:
        try:
            session = _dict(await self.sessions.retrieve(session_id))
            roots = await self._roots(session_id)
        except Exception:
            raise Unknown() from None
        if not roots:
            return ProviderSnapshot(
                session_id=session_id,
                root_status="idle" if session["status"] == "idle" else "unknown",
            )
        turn = roots[0]
        status = {
            "queued": "running",
            "in_progress": "running",
            "waiting": "waiting_tool",
            "completed": "completed",
            "failed": "failed",
            "cancelled": "cancelled",
        }.get(turn["status"], "unknown")
        calls = []
        for action in session.get("required_actions", []):
            if action.get("type") == "function_call" and action.get("turn_id") == turn["id"]:
                try:
                    calls.append(
                        PendingToolCall(
                            session_id=session_id,
                            **{k: action[k] for k in ("turn_id", "call_id", "name", "arguments")},
                        )
                    )
                except ValueError, KeyError, TypeError:
                    raise Unknown() from None
        if calls:
            status = "waiting_tool"
        response = None
        item_id = None
        if status == "completed" and include_response:
            items = await self._list_items(session_id, only_turn=turn["id"])
            matching = [item for item in items if item.turn_id == turn["id"]]
            if matching:
                response, item_id = matching[-1].response, matching[-1].id
        return ProviderSnapshot(
            session_id=session_id,
            root_turn_id=turn["id"],
            root_status=status,
            input_run_id=self.correlations.get((session_id, turn["id"]))
            or (session.get("metadata", {}).get("initial_run_id") if len(roots) == 1 else None),
            pending_calls=tuple(calls),
            response=response,
            item_id=item_id,
        )

    async def submit_input(self, session_id: str, content: str, run_id: str) -> str:
        before = await self._snapshot(session_id, include_response=False)
        if before.root_status not in {"idle", "completed", "failed", "cancelled"}:
            raise InvalidTransition()
        try:
            await self.sessions.events.create(
                session_id,
                idempotency_key=run_id,
                events=[
                    {
                        "type": "agent.session.input.message",
                        "input": [
                            {"role": "user", "content": [{"type": "input_text", "text": content}]}
                        ],
                    }
                ],
            )
            deadline = asyncio.get_running_loop().time() + 5
            while True:
                roots = await self._roots(session_id)
                if roots and roots[0]["id"] != before.root_turn_id:
                    break
                if asyncio.get_running_loop().time() >= deadline:
                    raise Unknown()
                await asyncio.sleep(0.1)
            turn_id = roots[0]["id"]
            self.correlations[(session_id, turn_id)] = run_id
            return turn_id
        except Exception:
            raise Unknown() from None

    @asynccontextmanager
    async def stream_events(self, session_id: str) -> AsyncIterator[_Events]:
        # Do not catch consumer exceptions across yield (e.g. InvalidOutput).
        try:
            manager = await self.sessions.events.stream(session_id)
            raw = await manager.__aenter__()
        except Exception:
            raise Unknown() from None
        try:
            yield _Events(raw, session_id)
        finally:
            try:
                await manager.__aexit__(None, None, None)
            except Exception:
                raise Unknown() from None

    async def submit_tool_result(self, call: PendingToolCall, result: ToolResult) -> None:
        key = (call.session_id, call.turn_id, call.call_id)
        previous = self.deliveries.get(key)
        if previous is not None and previous != (call, result):
            raise IdempotencyConflict()
        current = await self.inspect_session(call.session_id)
        if call not in current.pending_calls:
            raise InvalidTransition()
        self.deliveries[key] = (call, result)
        event = {
            "type": "agent.session.input.tool_result",
            "turn_id": call.turn_id,
            "call_id": call.call_id,
            "success": result.error is None,
        }
        if result.error:
            event["error"] = result.error
        else:
            event["output"] = result.model_dump_json()
        try:
            await self.sessions.events.create(
                call.session_id,
                idempotency_key=f"tool:{call.turn_id}:{call.call_id}",
                events=[event],
            )
        except Exception:
            raise Unknown() from None

    async def list_items(self, session_id: str) -> tuple[ProviderItem, ...]:
        return await self._list_items(session_id)

    async def _list_items(
        self, session_id: str, only_turn: str | None = None
    ) -> tuple[ProviderItem, ...]:
        try:
            roots = {turn["id"]: turn for turn in await self._roots(session_id)}
            raw_items = [
                _dict(item)
                async for item in self.sessions.items.list(session_id, order="asc", limit=100)
            ]
        except Exception:
            raise Unknown() from None
        items = []
        for item in raw_items:
            turn_id = item.get("turn_id")
            if (
                (only_turn is not None and turn_id != only_turn)
                or item.get("type") != "message"
                or item.get("role") != "assistant"
                or item.get("phase") == "commentary"
                or item.get("status", "completed") != "completed"
                or turn_id not in roots
                or roots[turn_id]["status"] != "completed"
            ):
                continue
            text = "".join(
                part.get("text", "")
                for part in item.get("content", [])
                if part.get("type") == "output_text"
            )
            try:
                sources = (
                    await self.source_loader(session_id, turn_id) if self.source_loader else ()
                )
            except Exception:
                raise Unknown() from None
            response: ApplicationResponse = normalize_response(text, sources)
            items.append(ProviderItem(id=item["id"], turn_id=turn_id, response=response))
        return tuple(items)

    async def cancel_turn(self, session_id: str, turn_id: str) -> None:
        current = await self.inspect_session(session_id)
        if current.root_turn_id != turn_id:
            raise InvalidTransition()
        if current.root_status in {"completed", "failed", "cancelled"}:
            return
        try:
            await self.sessions.events.create(
                session_id, events=[{"type": "agent.session.input.cancel"}]
            )
        except Exception:
            raise Unknown() from None

    async def delete_session(self, session_id: str) -> None:
        try:
            await self.sessions.delete(session_id)
        except Exception as error:
            if getattr(error, "status_code", None) == 404:
                return  # Known session is already absent; cleanup is idempotent.
            raise Unknown() from None


def build_live_provider(
    source_loader: SourceLoader | None = None,
    *,
    api_key: str | None = None,
    model: str | None = None,
) -> OpenAIAgentsProvider:
    """Create a client without network work; credentials stay in the application."""
    import os

    key = api_key or os.environ.get("OPENAI_API_KEY")
    chosen_model = model or os.environ.get("OPENAI_MODEL", "")
    if not key or not chosen_model.strip():
        raise ConfigurationConflict()
    try:
        from openai import AsyncOpenAI
    except ImportError:
        raise ConfigurationConflict() from None
    provider = OpenAIAgentsProvider(
        AsyncOpenAI(api_key=key, max_retries=0, timeout=20), source_loader
    )
    return provider
