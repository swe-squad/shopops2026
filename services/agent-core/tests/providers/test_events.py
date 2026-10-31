import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from app.contracts.errors import ConfigurationConflict, InvalidTransition, ProviderOutcomeUnknown
from app.contracts.models import ApplicationResponse
from app.contracts.tools import PendingToolCall, ToolResult
from app.providers.fake import FakeProvider, Scenario
from app.providers.openai_agents import OpenAIAgentsProvider


class Page:
    def __init__(self, rows):
        self.rows = rows

    def __aiter__(self):
        return self.iterate()

    async def iterate(self):
        for row in self.rows:
            yield row


class Sessions:
    def __init__(self):
        self.state = {"id": "session", "status": "idle", "required_actions": []}
        self.root = {"id": "turn", "subagent_id": None, "status": "in_progress"}
        self.turn_rows = []
        self.item_rows = []
        self.frames = []
        self.sent = []
        self.timeout = False
        self.deleted = False
        self.events = SimpleNamespace(create=self.send, stream=self.stream)
        self.turns = SimpleNamespace(list=lambda *a, **kw: Page(self.turn_rows))
        self.items = SimpleNamespace(list=lambda *a, **kw: Page(self.item_rows))

    async def retrieve(self, session_id):
        return self.state

    async def send(self, session_id, **kwargs):
        self.sent.append(kwargs)
        if self.timeout:
            raise TimeoutError("sensitive detail")
        event = kwargs["events"][0]
        if event["type"] == "agent.session.input.message":
            self.turn_rows = [self.root]
            self.state["status"] = "in_progress"
        if event["type"] == "agent.session.input.cancel":
            self.root["status"] = "cancelled"
            self.state["status"] = "idle"

    async def stream(self, session_id):
        return self._stream(session_id)

    @asynccontextmanager
    async def _stream(self, session_id):
        yield Page(self.frames)

    async def delete(self, session_id):
        self.deleted = True
        return {"id": session_id, "deleted": True}


def adapter():
    sessions = Sessions()
    client = SimpleNamespace(beta=SimpleNamespace(agents=SimpleNamespace(sessions=sessions)))
    return OpenAIAgentsProvider(client), sessions


def test_stream_loss_is_not_completion(config):
    async def exercise():
        for p, sid in [
            (FakeProvider([Scenario(interrupted=True)]), None),
            (adapter()[0], "session"),
        ]:
            if sid is None:
                sid = (await p.create_session(config, "c")).id
            async with p.stream_events(sid) as stream:
                await stream.wait_ready()
                await p.submit_input(sid, "message", "run")
                _ = [event async for event in stream]
            assert (await p.inspect_session(sid)).root_status == "running"

    asyncio.run(exercise())


def test_subagent_completion_does_not_complete_root():
    async def exercise():
        p, s = adapter()
        s.frames = [
            {
                "event_id": "e1",
                "session_id": "session",
                "turn_id": "child",
                "type": "agent.session.turn.completed",
                "turn": {"subagent_id": "specialist"},
            }
        ]
        s.turn_rows = [s.root]
        async with p.stream_events("session") as stream:
            events = [event async for event in stream]
        assert len(events) == 1 and not events[0].is_root
        assert (await p.inspect_session("session")).root_status == "running"

    asyncio.run(exercise())


def test_pending_actions_require_current_provider_state():
    async def exercise():
        p, s = adapter()
        call = PendingToolCall(
            session_id="session",
            turn_id="turn",
            call_id="call",
            name="get_return_metrics",
            arguments={"sku": "SKU-A"},
        )
        s.turn_rows = [s.root]
        with pytest.raises(InvalidTransition):
            await p.submit_tool_result(call, ToolResult(data={}))
        assert s.sent == []
        s.state["required_actions"] = [
            dict(call.model_dump(exclude={"session_id"}), type="function_call")
        ]
        s.state["status"] = "requires_action"
        await p.submit_tool_result(call, ToolResult(error="timeout"))
        assert s.sent[-1]["events"][0]["success"] is False
        assert s.sent[-1]["idempotency_key"] == "tool:turn:call"

    asyncio.run(exercise())


def test_timeout_submit_is_uncertain():
    async def exercise():
        p, s = adapter()
        s.timeout = True
        with pytest.raises(ProviderOutcomeUnknown) as error:
            await p.submit_input("session", "sensitive content", "run")
        assert str(error.value) == "provider_outcome_unknown"
        assert len(s.sent) == 1

    asyncio.run(exercise())


def test_live_create_requires_initial_input(config):
    async def exercise():
        p, s = adapter()
        with pytest.raises(ConfigurationConflict):
            await p.create_session(config, "conversation")
        assert s.sent == []

    asyncio.run(exercise())


def test_live_follow_up_inspection_items_and_cancel():
    async def exercise():
        p, s = adapter()
        async with p.stream_events("session") as stream:
            await stream.wait_ready()
            assert await p.submit_input("session", "hello", "run") == "turn"
        assert (await p.inspect_session("session")).input_run_id == "run"
        assert s.sent[0]["idempotency_key"] == "run"
        s.root["status"] = "completed"
        s.state["status"] = "idle"
        s.item_rows = [
            {
                "id": "item",
                "turn_id": "turn",
                "type": "message",
                "role": "assistant",
                "content": [
                    {
                        "type": "output_text",
                        "text": ApplicationResponse(
                            kind="clarification", text="Bạn muốn xem SKU nào?"
                        ).model_dump_json(),
                    }
                ],
            }
        ]
        snapshot = await p.inspect_session("session")
        assert snapshot.root_status == "completed"
        assert snapshot.response.kind == "clarification"
        assert len(await p.list_items("session")) == 1
        s.root["status"] = "in_progress"
        s.state["status"] = "in_progress"
        await p.cancel_turn("session", "turn")
        assert (await p.inspect_session("session")).root_status == "cancelled"
        await p.delete_session("session")
        assert s.deleted

    asyncio.run(exercise())


def test_required_actions_event_uses_nested_session_identity():
    async def exercise():
        p, s = adapter()
        s.frames = [
            {
                "event_id": "pending",
                "type": "agent.session.requires_action",
                "session": {
                    "id": "session",
                    "required_actions": [
                        {
                            "type": "function_call",
                            "turn_id": "turn",
                            "call_id": "call",
                            "name": "get_return_metrics",
                            "arguments": {},
                        }
                    ],
                },
            }
        ]
        async with p.stream_events("session") as stream:
            events = [event async for event in stream]
        assert len(events) == 1
        assert events[0].kind == "tool_pending"
        assert events[0].turn_id == "turn"

    asyncio.run(exercise())


def test_commentary_is_not_application_output():
    async def exercise():
        p, s = adapter()
        s.root["status"] = "completed"
        s.turn_rows = [s.root]
        s.item_rows = [
            {
                "id": "commentary",
                "turn_id": "turn",
                "type": "message",
                "role": "assistant",
                "phase": "commentary",
                "status": "completed",
                "content": [{"type": "output_text", "text": "Đang xem dữ liệu..."}],
            }
        ]
        assert await p.list_items("session") == ()

    asyncio.run(exercise())


def test_tool_result_replay_cannot_change_payload():
    async def exercise():
        from app.contracts.errors import IdempotencyConflict

        p, s = adapter()
        call = PendingToolCall(
            session_id="session",
            turn_id="turn",
            call_id="call",
            name="get_return_metrics",
            arguments={},
        )
        s.turn_rows = [s.root]
        s.state["required_actions"] = [
            dict(call.model_dump(exclude={"session_id"}), type="function_call")
        ]
        await p.submit_tool_result(call, ToolResult(data={"value": 1}))
        with pytest.raises(IdempotencyConflict):
            await p.submit_tool_result(call, ToolResult(data={"value": 2}))
        assert len(s.sent) == 1

    asyncio.run(exercise())


def test_sdk_stream_call_must_be_awaited():
    async def exercise():
        p, s = adapter()
        original = s.events.stream

        async def sdk_stream(session_id):
            return await original(session_id)

        s.events.stream = sdk_stream
        async with p.stream_events("session") as stream:
            await stream.wait_ready()
            assert [event async for event in stream] == []

    asyncio.run(exercise())


def test_bad_historical_output_does_not_block_new_input():
    async def exercise():
        p, s = adapter()
        old = {"id": "old", "subagent_id": None, "status": "completed"}
        s.turn_rows = [old]
        s.item_rows = [
            {
                "id": "bad",
                "turn_id": "old",
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "invalid JSON"}],
            }
        ]
        assert await p.submit_input("session", "new request", "new-run") == "turn"
        s.root["status"] = "completed"
        s.item_rows.append(
            {
                "id": "good",
                "turn_id": "turn",
                "type": "message",
                "role": "assistant",
                "content": [
                    {"type": "output_text", "text": '{"kind":"clarification","text":"SKU nào?"}'}
                ],
            }
        )
        assert (await p.inspect_session("session")).response.text == "SKU nào?"

    asyncio.run(exercise())


def test_create_session_submits_initial_input_atomically(config):
    from unittest.mock import AsyncMock

    async def exercise():
        p, sessions = adapter()
        sessions.create = AsyncMock(
            return_value={"id": "session", "metadata": {"initial_run_id": "run"}}
        )
        created = await p.create_session(config, "run", initial_input="synthetic first message")
        assert created.id == "session" and created.input_submitted
        args = sessions.create.call_args.kwargs
        assert args["input"] == "synthetic first message"
        assert args["environment"] == {"type": "none"}
        assert args["metadata"]["initial_run_id"] == "run"
        assert args["agent"]["model"] == config.model
        assert args["agent"]["tools"][0]["type"] == "function"
        assert sessions.sent == []

    asyncio.run(exercise())


def test_definitive_create_rejection_is_sanitized(config):
    from unittest.mock import AsyncMock

    from app.contracts.errors import ProviderRequestRejected

    class Rejected(Exception):
        status_code = 403

    async def exercise():
        provider, sessions = adapter()
        sessions.create = AsyncMock(side_effect=Rejected("sensitive upstream body"))
        with pytest.raises(ProviderRequestRejected) as error:
            await provider.create_session(config, "run", initial_input="hello")
        assert str(error.value) == "provider_request_rejected"
        assert sessions.create.call_count == 1

    asyncio.run(exercise())
