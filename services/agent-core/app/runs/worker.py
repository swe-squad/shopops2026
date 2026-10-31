import asyncio
import json
import logging
import time
from collections import Counter
from collections.abc import Callable
from contextlib import suppress
from datetime import datetime, timedelta

from app.contracts.errors import (
    ArtifactInvalid,
    ArtifactUnavailable,
    InvalidOutput,
    ProviderOutcomeUnknown,
    ProviderRequestRejected,
)
from app.contracts.models import TERMINAL, ConfigSnapshot, Run
from app.contracts.provider import AgentProvider, ProviderSnapshot
from app.contracts.repository import Repository
from app.contracts.tools import ToolBridge, ToolResult
from app.runs.artifacts import finalize_artifacts
from app.runs.recovery import matches_root
from app.storage.repositories import utcnow

ACTIVE = ("running", "waiting_tool", "reconciling")


def provider_input(config: ConfigSnapshot, output_mode: str, content: str) -> str:
    if config.runtime_profile.environment_type == "none":
        return content
    directive = (
        "For an answer, use approved skills and write the canonical Vietnamese report to "
        "/workspace/outputs/report.json using the registered report schema and root-turn "
        "metrics/knowledge evidence. Clarification or cannot_answer needs no report."
        if output_mode == "report"
        else "Return a Vietnamese text response. No report artifact is required for this turn."
    )
    return content + "\n\n[Application output format for this turn]\n" + directive


class RunWorker:
    def __init__(
        self,
        repository: Repository,
        provider: AgentProvider,
        bridge: ToolBridge,
        *,
        clock: Callable[[], datetime] = utcnow,
        max_concurrent: int = 4,
        max_tool_calls: int = 8,
        mcp_timeout: float = 15,
    ) -> None:
        self.repo = repository
        self.provider = provider
        self.bridge = bridge
        self.clock = clock
        self.max_concurrent = max_concurrent
        self.max_tool_calls = max_tool_calls
        self.mcp_timeout = mcp_timeout
        self.heartbeat: datetime | None = None
        self.metrics: Counter = Counter()
        self.stopping = asyncio.Event()
        self._active: dict[str, asyncio.Task] = {}
        self.failure: str | None = None
        self._reported: set[str] = set()

    async def startup(self) -> None:
        await self.repo.recover_interrupted()
        self.heartbeat = self.clock()

    async def _current(self, run: Run) -> Run:
        c, _ = await self.repo.execution_context(run.id)
        return await self.repo.get_run(c.scope, run.id)

    async def _uncertain(self, run: Run) -> None:
        current = await self._current(run)
        if current.state in TERMINAL:
            return
        if self.clock() >= run.recovery_deadline:
            await self.repo.transition_run(
                run.id, ACTIVE, "failed", error="provider_outcome_unknown", block=True
            )
        elif current.state != "reconciling":
            await self.repo.transition_run(run.id, ACTIVE, "reconciling")

    async def _inspect(self, run: Run, session_id: str) -> ProviderSnapshot:
        remaining = (run.recovery_deadline - self.clock()).total_seconds()
        if remaining <= 0:
            raise ProviderOutcomeUnknown()
        async with asyncio.timeout(min(15, remaining)):
            snapshot = await self.provider.inspect_session(session_id)
        if snapshot.session_id != session_id:
            raise ProviderOutcomeUnknown()
        return snapshot

    async def _cancel(self, run: Run, snapshot: ProviderSnapshot) -> ProviderSnapshot:
        if snapshot.root_turn_id is None:
            raise ProviderOutcomeUnknown()
        try:
            async with asyncio.timeout(
                min(15, max(0.01, (run.recovery_deadline - self.clock()).total_seconds()))
            ):
                await self.provider.cancel_turn(snapshot.session_id, snapshot.root_turn_id)
        except Exception:
            self.metrics["provider_errors"] += 1
        return await self._inspect(run, snapshot.session_id)

    async def _consume(self, run: Run, snapshot: ProviderSnapshot) -> bool:
        """Use inspected required_actions/root state, never stream closure, as authority."""
        run = await self._current(run)
        if run.state in TERMINAL:
            return True
        if snapshot.environment is not None:
            c, _ = await self.repo.execution_context(run.id)
            await self.repo.save_runtime(c.scope, c.id, snapshot.environment)
            environment = snapshot.environment
            expired = environment.state == "provisioning" and self.clock() >= min(
                run.deadline,
                (run.runtime_setup_started_at or run.created_at)
                + timedelta(seconds=run.config.runtime_profile.setup_timeout_seconds),
            )
            if environment.state in ("failed", "unavailable") or expired:
                if snapshot.root_status not in ("completed", "failed", "cancelled"):
                    snapshot = await self._cancel(run, snapshot)
                    if snapshot.root_status not in ("completed", "failed", "cancelled"):
                        raise ProviderOutcomeUnknown()
                error = (
                    "environment_timeout"
                    if expired
                    else "environment_unavailable"
                    if environment.state == "unavailable"
                    else "environment_failed"
                )
                await self.repo.transition_run(run.id, ACTIVE, "failed", error=error, block=True)
                return True
            if environment.state == "provisioning":
                await self.repo.append_event(
                    run.id,
                    "environment.provisioning",
                    provider_event_id="environment:" + environment.id,
                )
                return False
        if not matches_root(run, snapshot):
            await self._uncertain(run)
            return False
        if run.provider_turn_id is None:
            await self.repo.mark_submission(run.id, "submitted", snapshot.root_turn_id)
            run = await self._current(run)
        if snapshot.root_status in ("running", "waiting_tool") and self.clock() >= run.deadline:
            snapshot = await self._cancel(run, snapshot)
            if not matches_root(run, snapshot):
                raise ProviderOutcomeUnknown()
        if snapshot.root_status == "completed":
            try:
                response, item_id = snapshot.response, snapshot.item_id
                if response is None or item_id is None:
                    async with asyncio.timeout(15):
                        items = await self.provider.list_items(snapshot.session_id)
                    matches = [item for item in items if item.turn_id == run.provider_turn_id]
                    if len(matches) != 1:
                        raise InvalidOutput()
                    response, item_id = matches[0].response, matches[0].id
                remaining = (run.deadline - self.clock()).total_seconds()
                async with asyncio.timeout(max(0.01, remaining)):
                    await finalize_artifacts(
                        self.repo,
                        self.provider,
                        run,
                        snapshot.session_id,
                        snapshot.root_turn_id,
                        response,
                    )
                await self.repo.complete_run(run.id, snapshot.root_turn_id, item_id, response)
            except ArtifactInvalid, ArtifactUnavailable:
                await self.repo.transition_run(run.id, ACTIVE, "failed", error="artifact_invalid")
            except TimeoutError:
                await self.repo.transition_run(run.id, ACTIVE, "failed", error="run_timeout")
            except InvalidOutput:
                await self.repo.transition_run(run.id, ACTIVE, "failed", error="invalid_output")
            return True
        if snapshot.root_status in ("failed", "cancelled"):
            await self.repo.transition_run(
                run.id,
                ACTIVE,
                snapshot.root_status,
                error="run_timeout"
                if self.clock() >= run.deadline
                else "provider_failed"
                if snapshot.root_status == "failed"
                else None,
            )
            return True
        if self.clock() >= run.deadline:
            await self._uncertain(run)
            return False
        if snapshot.root_status == "waiting_tool":
            await self.repo.transition_run(run.id, ("running", "reconciling"), "waiting_tool")
            for call in snapshot.pending_calls:
                pending = await self._inspect(run, snapshot.session_id)
                if not matches_root(run, pending):
                    raise ProviderOutcomeUnknown()
                if self.clock() >= run.deadline or pending.root_status in TERMINAL:
                    return await self._consume(run, pending)
                if call not in pending.pending_calls:
                    continue
                if call.session_id != snapshot.session_id or call.turn_id != snapshot.root_turn_id:
                    raise ProviderOutcomeUnknown()
                cached = await self.repo.get_tool_result(run.id, call)
                if cached is None:
                    if not await self.repo.begin_tool_call(run.id, call, self.max_tool_calls):
                        cancelled = await self._cancel(run, snapshot)
                        return (
                            await self._consume(run, cancelled)
                            if cancelled.root_status in ("completed", "failed", "cancelled")
                            else False
                        )
                    names = {t.name for t in self.bridge.definitions(run.config)}
                    if call.name not in run.config.capabilities or call.name not in names:
                        result = ToolResult(error="permission_denied")
                    else:
                        c, _ = await self.repo.execution_context(run.id)
                        tool_started = time.monotonic()
                        try:
                            async with asyncio.timeout(
                                min(
                                    self.mcp_timeout,
                                    max(0.01, (run.deadline - self.clock()).total_seconds()),
                                )
                            ):
                                result = await self.bridge.execute(c.scope, c.id, run.config, call)
                        except TimeoutError:
                            result = ToolResult(error="timeout")
                        except Exception:
                            result = ToolResult(error="upstream_unavailable")
                        self.metrics["tool_latency_seconds"] += time.monotonic() - tool_started
                        self.metrics["tool_calls"] += 1
                        if result.error:
                            self.metrics["mcp_errors"] += 1
                    try:
                        result = await self.repo.record_tool_result(run.id, call, result)
                    except InvalidOutput:
                        result = await self.repo.record_tool_result(
                            run.id, call, ToolResult(error="invalid_input")
                        )
                else:
                    result, _ = cached
                # Re-read current required actions immediately before mutation/delivery.
                current = await self._inspect(run, snapshot.session_id)
                if self.clock() >= run.deadline or current.root_status in TERMINAL:
                    return await self._consume(run, current)
                if not matches_root(run, current) or call not in current.pending_calls:
                    continue
                async with asyncio.timeout(
                    min(15, max(0.01, (run.deadline - self.clock()).total_seconds()))
                ):
                    await self.provider.submit_tool_result(call, result)
                await self.repo.mark_tool_delivered(run.id, call)
            await self.repo.transition_run(run.id, ("waiting_tool",), "running")
            return await self._consume_after_tools(run, snapshot)
        return False

    async def _consume_after_tools(self, run: Run, previous: ProviderSnapshot) -> bool:
        snapshot = await self._inspect(run, previous.session_id)
        if snapshot.root_status in ("completed", "failed", "cancelled"):
            return await self._consume(run, snapshot)
        return False

    async def execute(self, run: Run) -> None:
        try:
            c, message = await self.repo.execution_context(run.id)
            if run.submission_marker != "none":
                await self.reconcile(run)
                return
            if self.clock() >= run.deadline:
                await self.repo.transition_run(run.id, ACTIVE, "failed", error="run_timeout")
                return
            session_id = c.provider_session_id
            if session_id is None:
                await self.repo.mark_submission(run.id, "session_creating")
                async with asyncio.timeout(
                    max(0.01, (run.deadline - self.clock()).total_seconds())
                ):
                    session = await self.provider.create_session(
                        run.config,
                        run.id,
                        initial_input=provider_input(run.config, run.output_mode, message.content),
                    )
                session_id = session.id
                await self.repo.save_session_mapping(
                    run.id, session_id, input_submitted=session.input_submitted
                )
                if session.environment is not None:
                    await self.repo.save_runtime(c.scope, c.id, session.environment)
                if session.input_submitted:
                    # Persist the accepted input before inspecting any remote turn. No re-send.
                    await self.repo.mark_submission(run.id, "submitted")
                    await self.reconcile(await self._current(run))
                    return
                await self.repo.mark_submission(run.id, "none")
            snapshot = await self._inspect(run, session_id)
            if snapshot.root_status not in ("idle", "completed", "failed", "cancelled"):
                raise ProviderOutcomeUnknown()
            async with asyncio.timeout(max(0.01, (run.deadline - self.clock()).total_seconds())):
                async with self.provider.stream_events(session_id) as stream:
                    await stream.wait_ready()
                    await self.repo.mark_submission(run.id, "submitting")
                    turn_id = await self.provider.submit_input(
                        session_id,
                        provider_input(run.config, run.output_mode, message.content),
                        run.id,
                    )
                    await self.repo.mark_submission(run.id, "submitted", turn_id)
                    run = await self._current(run)
                    if await self._consume(run, await self._inspect(run, session_id)):
                        return
                    iterator = stream.__aiter__()
                    while True:
                        try:
                            async with asyncio.timeout(0.5):
                                event = await anext(iterator)
                        except TimeoutError, StopAsyncIteration:
                            break
                        if (
                            event.is_root
                            and event.session_id == session_id
                            and event.turn_id == turn_id
                        ):
                            await self.repo.append_event(
                                run.id, "run.observed", provider_event_id=event.id
                            )
                            if await self._consume(run, await self._inspect(run, session_id)):
                                return
                        elif event.kind == "tool_pending":
                            await self.reconcile(await self._current(run))
                            return
            await self.reconcile(run)
        except ProviderRequestRejected:
            await self.repo.transition_run(
                run.id, ACTIVE, "failed", error="provider_request_rejected"
            )
        except asyncio.CancelledError:
            await self._uncertain(run)
            raise
        except Exception:
            self.metrics["provider_errors"] += 1
            await self._uncertain(run)

    async def reconcile(self, run: Run) -> None:
        try:
            run = await self._current(run)
            if run.state in TERMINAL:
                return
            if self.clock() >= run.recovery_deadline:
                await self._uncertain(run)
                return
            c, _ = await self.repo.execution_context(run.id)
            if c.provider_session_id is None:
                await self._uncertain(run)
                return
            snapshot = await self._inspect(run, c.provider_session_id)
            if run.submission_marker == "session_creating" and snapshot.root_status == "idle":
                await self.repo.mark_submission(run.id, "none")
                await self.repo.transition_run(run.id, ("reconciling",), "running")
                await self.execute(await self._current(run))
                return
            if not await self._consume(run, snapshot):
                await self._uncertain(run)
        except asyncio.CancelledError:
            raise
        except Exception:
            self.metrics["provider_errors"] += 1
            await self._uncertain(run)

    async def _perform(self, run: Run) -> None:
        started = time.monotonic()
        if run.submission_marker == "none":
            self.metrics["queue_delay_seconds"] += max(
                0, (self.clock() - run.created_at).total_seconds()
            )
        if run.state == "running" and run.submission_marker == "none":
            await self.execute(run)
        else:
            await self.reconcile(run)
        current = await self._current(run)
        if current.state in TERMINAL and run.id not in self._reported:
            self._reported.add(run.id)
            self.metrics[f"runs.{current.state}"] += 1
            elapsed = time.monotonic() - started
            self.metrics["run_latency_seconds"] += elapsed
            logging.getLogger("agent_core.worker").info(
                json.dumps(
                    {
                        "run_id": run.id,
                        "status": current.state,
                        "latency_seconds": elapsed,
                        "error": current.error,
                    }
                )
            )

    async def tick(self) -> None:
        pending = list(await self.repo.pending_runs())[: self.max_concurrent]
        while len(pending) < self.max_concurrent:
            run = await self.repo.claim_next_run()
            if run is None:
                break
            pending.append(run)
        await asyncio.gather(*(self._perform(r) for r in pending))
        self.heartbeat = self.clock()

    async def serve(self) -> None:
        """Schedule each run independently so one long stream cannot starve free slots."""
        await self.startup()
        try:
            while not self.stopping.is_set():
                for key, task in tuple(self._active.items()):
                    if task.done():
                        task.result()
                        del self._active[key]
                pending = [r for r in await self.repo.pending_runs() if r.id not in self._active]
                for run in pending:
                    if len(self._active) >= self.max_concurrent:
                        break
                    self._active[run.id] = asyncio.create_task(self._perform(run))
                while len(self._active) < self.max_concurrent:
                    run = await self.repo.claim_next_run()
                    if run is None:
                        break
                    self._active[run.id] = asyncio.create_task(self._perform(run))
                self.heartbeat = self.clock()
                with suppress(TimeoutError):
                    await asyncio.wait_for(self.stopping.wait(), timeout=0.1)
        except Exception:
            self.failure = "worker_unavailable"
            raise
        finally:
            for task in self._active.values():
                task.cancel()
            await asyncio.gather(*self._active.values(), return_exceptions=True)
            self._active.clear()
            self.heartbeat = None

    async def stop(self) -> None:
        self.stopping.set()
