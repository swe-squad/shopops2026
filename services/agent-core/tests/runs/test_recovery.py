import asyncio
from datetime import timedelta

import pytest

from app.contracts.errors import ConversationBusy
from app.contracts.models import ApplicationResponse, Source
from app.contracts.provider import ProviderEvent, ProviderSnapshot
from app.contracts.tools import PendingToolCall
from tests.runs.doubles import Clock, ControlledBridge, ControlledProvider
from tests.storage.test_repositories import conversation


async def setup(repo, scope, mode="answer"):
    from app.runs.worker import RunWorker

    c = await conversation(repo, scope)
    result = await repo.enqueue_message(scope, c.id, "m", "hello")
    provider, bridge = ControlledProvider(mode), ControlledBridge()
    clock = Clock(repo.clock())
    worker = RunWorker(repo, provider, bridge, clock=clock)
    return c, result, provider, bridge, worker, clock


def test_only_one_active_run_per_conversation(repo, scope):
    async def execute():
        c = await conversation(repo, scope)

        async def submit(key):
            try:
                return await repo.enqueue_message(scope, c.id, key, "hello")
            except ConversationBusy:
                return None

        results = await asyncio.gather(*(submit(str(i)) for i in range(8)))
        assert sum(r is not None for r in results) == 1
        claims = await asyncio.gather(*(repo.claim_next_run() for _ in range(8)))
        assert sum(r is not None for r in claims) == 1

    asyncio.run(execute())


def test_restart_resumes_queued_run(repo, scope):
    async def execute():
        c, result, provider, _, worker, _ = await setup(repo, scope)
        await worker.startup()
        await worker.tick()
        assert (await repo.get_run(scope, result.run.id)).state == "completed"
        assert [m.role for m in (await repo.get_history(scope, c.id)).items] == [
            "user",
            "assistant",
        ]
        assert len(provider.submissions) == 1

    asyncio.run(execute())


def test_replayed_tool_result_not_executed_again(repo, scope):
    async def execute():
        _, result, provider, bridge, worker, _ = await setup(repo, scope, "tool")
        run = await repo.claim_next_run()
        await repo.save_session_mapping(run.id, "session-a")
        await repo.mark_submission(run.id, "submitted", "turn-a")
        call = PendingToolCall(
            session_id="session-a",
            turn_id="turn-a",
            call_id="call-a",
            name="search_knowledge",
            arguments={"query": "policy"},
        )
        await repo.begin_tool_call(run.id, call, 8)
        value = await bridge.execute(scope, run.conversation_id, run.config, call)
        await repo.record_tool_result(run.id, call, value)
        provider.snapshot = ProviderSnapshot(
            session_id="session-a",
            root_turn_id="turn-a",
            root_status="waiting_tool",
            input_run_id=run.id,
            pending_calls=(call,),
        )
        await worker.startup()
        await worker.tick()
        assert bridge.executions == 1
        assert (await repo.get_run(scope, result.run.id)).state == "completed"
        assert provider.submissions == []

    asyncio.run(execute())


def test_unknown_submission_blocks_conversation(repo, scope):
    async def execute():
        c, result, provider, _, worker, clock = await setup(repo, scope, "unknown")
        await worker.tick()
        assert (await repo.get_run(scope, result.run.id)).state == "reconciling"
        clock.value = result.run.recovery_deadline + timedelta(seconds=1)
        await worker.tick()
        failed = await repo.get_run(scope, result.run.id)
        assert failed.state == "failed" and failed.error == "provider_outcome_unknown"
        assert (await repo.get_conversation(scope, c.id)).status == "blocked"
        assert len(provider.submissions) == 1
        with pytest.raises(ConversationBusy):
            await repo.enqueue_message(scope, c.id, "next", "hello again")

    asyncio.run(execute())


def test_stream_closure_and_subagent_completion_keep_root_locked(repo, scope):
    async def execute():
        c, result, provider, _, worker, _ = await setup(repo, scope, "active")
        provider.events = [
            ProviderEvent(
                id="event-1",
                session_id="session-a",
                turn_id="subagent-turn",
                kind="completed",
                is_root=False,
            )
        ]
        await worker.tick()
        assert (await repo.get_run(scope, result.run.id)).state == "reconciling"
        with pytest.raises(ConversationBusy):
            await repo.enqueue_message(scope, c.id, "next", "hello")

    asyncio.run(execute())


@pytest.mark.parametrize("confirmed", [True, False])
def test_timeout_unlocks_only_after_confirmed_cancel(repo, scope, confirmed):
    async def execute():
        c, result, provider, _, worker, clock = await setup(repo, scope, "active")
        provider.cancel_confirmed = confirmed
        await worker.tick()
        clock.value = result.run.deadline + timedelta(seconds=1)
        await worker.tick()
        assert provider.cancel_requested
        run = await repo.get_run(scope, result.run.id)
        assert run.state == ("cancelled" if confirmed else "reconciling")
        if confirmed:
            await repo.enqueue_message(scope, c.id, "next", "hello")
        else:
            with pytest.raises(ConversationBusy):
                await repo.enqueue_message(scope, c.id, "next", "hello")

    asyncio.run(execute())


def test_unknown_session_creation_never_creates_replacement(repo, scope):
    async def execute():
        _, result, provider, _, worker, clock = await setup(repo, scope)
        run = await repo.claim_next_run()
        await repo.mark_submission(run.id, "session_creating")
        await worker.startup()
        clock.value = result.run.recovery_deadline + timedelta(seconds=1)
        await worker.tick()
        assert provider.creations == 0
        assert (await repo.get_run(scope, run.id)).error == "provider_outcome_unknown"

    asyncio.run(execute())


def test_unknown_sources_fail_without_publishing_assistant(repo, scope):
    async def execute():
        c, result, provider, _, worker, _ = await setup(repo, scope, "active")
        await worker.tick()
        provider.snapshot = provider.snapshot.model_copy(
            update={
                "root_status": "completed",
                "item_id": "item-a",
                "response": ApplicationResponse(
                    kind="answer",
                    text="Invalid",
                    sources=(Source(type="data", reference="fabricated"),),
                ),
            }
        )
        await worker.tick()
        assert (await repo.get_run(scope, result.run.id)).error == "invalid_output"
        assert len((await repo.get_history(scope, c.id)).items) == 1

    asyncio.run(execute())


def test_duplicate_provider_events_do_not_duplicate_history(repo, scope):
    async def execute():
        c, result, provider, _, worker, _ = await setup(repo, scope, "active")
        event = ProviderEvent(id="event-1", session_id="session-a", turn_id="turn-a", kind="status")
        provider.events = [event, event]
        await worker.tick()
        events = (await repo.get_events(scope, result.run.id)).items
        assert sum(e.provider_event_id == "event-1" for e in events) == 1
        provider.snapshot = provider.snapshot.model_copy(
            update={
                "root_status": "completed",
                "item_id": "item-a",
                "response": ApplicationResponse(kind="answer", text="Xong."),
            }
        )
        await worker.tick()
        await worker.tick()
        assert len((await repo.get_history(scope, c.id)).items) == 2

    asyncio.run(execute())


def test_maximum_tool_calls_cancels_instead_of_executing_ninth(repo, scope):
    async def execute():
        _, result, provider, bridge, worker, _ = await setup(repo, scope, "active")
        await worker.tick()
        run = await repo.get_run(scope, result.run.id)
        for i in range(8):
            call = PendingToolCall(
                session_id="session-a",
                turn_id="turn-a",
                call_id=str(i),
                name="search_knowledge",
                arguments={"query": "policy"},
            )
            await repo.begin_tool_call(run.id, call, 8)
            await repo.record_tool_result(
                run.id, call, await bridge.execute(scope, run.conversation_id, run.config, call)
            )
        ninth = PendingToolCall(
            session_id="session-a",
            turn_id="turn-a",
            call_id="ninth",
            name="search_knowledge",
            arguments={"query": "policy"},
        )
        provider.snapshot = provider.snapshot.model_copy(
            update={"root_status": "waiting_tool", "pending_calls": (ninth,)}
        )
        await worker.tick()
        assert bridge.executions == 8
        assert provider.cancel_requested
        assert (await repo.get_run(scope, run.id)).state == "cancelled"

    asyncio.run(execute())


def test_worker_records_status_and_latency_metrics(repo, scope):
    async def execute():
        _, _, _, _, worker, _ = await setup(repo, scope)
        await worker.tick()
        assert worker.metrics["runs.completed"] == 1
        assert worker.metrics["run_latency_seconds"] >= 0
        assert worker.metrics["queue_delay_seconds"] >= 0

    asyncio.run(execute())


def test_confirmed_completion_with_missing_output_fails_without_blocking(repo, scope):
    async def execute():
        c, result, provider, _, worker, _ = await setup(repo, scope, "active")
        await worker.tick()
        provider.snapshot = provider.snapshot.model_copy(
            update={"root_status": "completed", "response": None, "item_id": None}
        )
        await worker.tick()
        failed = await repo.get_run(scope, result.run.id)
        assert failed.state == "failed" and failed.error == "invalid_output"
        assert (await repo.get_conversation(scope, c.id)).status == "active"
        await repo.enqueue_message(scope, c.id, "next", "next")

    asyncio.run(execute())


def test_tool_finishing_after_deadline_is_not_delivered(repo, scope):
    async def execute():
        _, result, provider, bridge, worker, clock = await setup(repo, scope, "tool")
        original = bridge.execute

        async def finish_late(*args):
            value = await original(*args)
            clock.value = result.run.deadline + timedelta(seconds=1)
            return value

        bridge.execute = finish_late
        await worker.tick()
        assert provider.results == []
        assert provider.cancel_requested
        assert (await repo.get_run(scope, result.run.id)).state == "cancelled"

    asyncio.run(execute())


def test_atomic_creation_never_submits_first_message_twice(repo, scope):
    from app.contracts.provider import ProviderSession
    from app.runs.worker import RunWorker

    class AtomicProvider(ControlledProvider):
        async def create_session(self, config, correlation_id, initial_input=None):
            self.creations += 1
            assert initial_input == "hello"
            self.ready = True
            await self.submit_input("session-a", initial_input, correlation_id)
            self.ready = False
            return ProviderSession(id="session-a", input_submitted=True)

    async def exercise():
        c = await conversation(repo, scope)
        message = await repo.enqueue_message(scope, c.id, "atomic", "hello")
        provider = AtomicProvider()
        worker = RunWorker(repo, provider, ControlledBridge())
        await worker.tick()
        assert (await repo.get_run(scope, message.run.id)).state == "completed"
        assert provider.submissions == [message.run.id]
        assert provider.creations == 1
        await worker.tick()
        assert provider.submissions == [message.run.id]

    asyncio.run(exercise())


def test_silent_live_stream_yields_to_saved_state_reconciliation(repo, scope):
    from contextlib import asynccontextmanager

    from tests.runs.doubles import Stream

    class SilentStream(Stream):
        async def events(self):
            await asyncio.Event().wait()
            yield  # async generator, deliberately never emits

    class SilentProvider(ControlledProvider):
        @asynccontextmanager
        async def stream_events(self, session_id):
            yield SilentStream(self)

    async def exercise():
        from app.runs.worker import RunWorker

        c = await conversation(repo, scope)
        result = await repo.enqueue_message(scope, c.id, "silent", "hello")
        provider = SilentProvider(mode="active")
        await asyncio.wait_for(RunWorker(repo, provider, ControlledBridge()).tick(), timeout=2)
        assert (await repo.get_run(scope, result.run.id)).state in {"running", "reconciling"}
        assert provider.submissions == [result.run.id]

    asyncio.run(exercise())
