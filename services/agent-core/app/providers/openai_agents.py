"""Official Agents API boundary: initial input is submitted atomically with creation."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path, PurePosixPath
from typing import Any

from pydantic import ValidationError

from app.contracts.errors import (
    ArtifactInvalid,
    ArtifactTransient,
    ArtifactUnavailable,
    ConfigurationConflict,
    IdempotencyConflict,
    InvalidTransition,
    ProviderRequestRejected,
)
from app.contracts.errors import ProviderOutcomeUnknown as Unknown
from app.contracts.models import ApplicationResponse, ConfigSnapshot, Source
from app.contracts.provider import ProviderEvent, ProviderItem, ProviderSession, ProviderSnapshot
from app.contracts.runtime import ProviderArtifact, ProviderEnvironment, RuntimeProfile
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
                owner = event.get(
                    "session_id",
                    event.get("session", {}).get("id", event.get("subagent", {}).get("session_id")),
                )
                if owner != self.session_id:
                    raise Unknown()
                activity = {
                    "agent.session.environment.pending": "environment.provisioning",
                    "agent.session.environment.ready": "environment.provisioning",
                    "agent.session.environment.connected": "environment.connected",
                    "agent.session.environment.failed": "environment.failed",
                    "agent.session.environment.expired": "environment.failed",
                    "agent.session.environment.disconnected": "environment.failed",
                    "agent.session.environment.suspended": "environment.failed",
                    "agent.session.subagent.created": "subagent.started",
                    "agent.session.subagent.active": "subagent.started",
                    "agent.session.subagent.closed": "subagent.completed",
                }.get(event.get("type"))
                item = event.get("item", {})
                if item.get("type") == "command_execution":
                    activity = {
                        "agent.session.turn.item.added": "command.started",
                        "agent.session.turn.item.done": "command.completed",
                    }.get(event.get("type"))
                if activity:
                    yield ProviderEvent(
                        id=event["event_id"],
                        session_id=self.session_id,
                        turn_id=event.get("turn_id") or item.get("turn_id"),
                        kind=activity,
                        is_root=False,
                    )
                    continue
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
    def __init__(
        self,
        client: Any,
        source_loader: SourceLoader | None = None,
        *,
        cleanup_timeout_seconds: float = 60,
        bundle_root: Path | None = None,
    ) -> None:
        if not 0 < cleanup_timeout_seconds <= 60:
            raise ConfigurationConflict()
        if hasattr(client, "with_options"):
            client = client.with_options(max_retries=0)
        self.client = client
        self.created_sessions: list[str] = []
        self.last_http_status: int | None = None
        self.last_error_fields: dict[str, str] = {}
        self.sessions = client.beta.agents.sessions
        self.deliveries: dict[tuple[str, str, str], tuple[PendingToolCall, ToolResult]] = {}
        self.source_loader = source_loader
        self.cleanup_timeout_seconds = cleanup_timeout_seconds
        self.bundle_root = bundle_root
        # Optimization only. Restart loses correlation, and recovery then blocks safely.
        self.correlations: dict[tuple[str, str], str] = {}

    async def create_session(
        self, config: ConfigSnapshot, correlation_id: str, *, initial_input: str | None = None
    ) -> ProviderSession:
        if initial_input is None or not initial_input.strip():
            raise ConfigurationConflict()
        try:
            profile = RuntimeProfile.model_validate(config.runtime_profile.model_dump())
        except ValidationError, ValueError, TypeError, AttributeError:
            raise ConfigurationConflict() from None
        from app.agents.capabilities import select_tools
        from app.agents.instructions import build_instructions
        from app.tools.validation import definitions

        tools = select_tools(config, definitions())
        environment = {"type": "none"}
        agent = {
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
        }
        if profile.environment_type == "openai_hosted":
            from app.agents.runtime_bundle import build_runtime_bundle
            from app.providers.hosted_runtime import build_hosted_environment

            bundle = (
                build_runtime_bundle(profile, bundle_root=self.bundle_root)
                if self.bundle_root is not None
                else build_runtime_bundle(profile)
            )
            environment = build_hosted_environment(profile, bundle)
            agent["multi_agent"] = {"enabled": True, "max_concurrent_subagents": 2}
        try:
            session = _dict(
                await self.sessions.create(
                    agent=agent,
                    environment=environment,
                    input=initial_input,
                    metadata={"initial_run_id": correlation_id},
                    output_type=ApplicationResponse,
                )
            )
            self.created_sessions.append(session["id"])
            runtime = None
            if environment["type"] == "openai_hosted":
                returned = session["environment"]
                if returned["type"] != "openai_hosted":
                    raise Unknown()
                # Persist known IDs/input receipt before any provisioning wait or extra I/O.
                runtime = ProviderEnvironment(id=returned["id"], state="provisioning")
            return ProviderSession(id=session["id"], input_submitted=True, environment=runtime)
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
            if session["id"] != session_id:
                raise Unknown()
            environment = await self._environment(session)
            roots = await self._roots(session_id)
        except Exception:
            raise Unknown() from None
        if not roots:
            return ProviderSnapshot(
                session_id=session_id,
                environment=environment,
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
        if (
            status == "completed"
            and include_response
            and (environment is None or environment.state == "connected")
        ):
            items = await self._list_items(session_id, only_turn=turn["id"])
            matching = [item for item in items if item.turn_id == turn["id"]]
            if matching:
                response, item_id = matching[-1].response, matching[-1].id
        return ProviderSnapshot(
            session_id=session_id,
            environment=environment,
            root_turn_id=turn["id"],
            root_status=status,
            input_run_id=self.correlations.get((session_id, turn["id"]))
            or (session.get("metadata", {}).get("initial_run_id") if len(roots) == 1 else None),
            pending_calls=tuple(calls),
            response=response,
            item_id=item_id,
        )

    async def _environment(self, session: dict) -> ProviderEnvironment | None:
        configuration = session.get("environment", {"type": "none"})
        if configuration["type"] == "none":
            return None
        if configuration["type"] != "openai_hosted":
            raise Unknown()
        environment_id = configuration["id"]
        try:
            state = _dict(await self.client.beta.agents.environments.retrieve(environment_id))
        except Exception as error:
            if getattr(error, "status_code", None) == 404:
                return ProviderEnvironment(
                    id=environment_id, state="unavailable", error="environment_unavailable"
                )
            raise Unknown() from None
        if state["id"] != environment_id or state["type"] != "openai_hosted":
            raise Unknown()
        status = state["status"]
        if status in {"pending", "ready"}:
            return ProviderEnvironment(id=environment_id, state="provisioning")
        if status == "connected":
            return ProviderEnvironment(id=environment_id, state="connected")
        if status == "failed":
            return ProviderEnvironment(
                id=environment_id, state="failed", error="environment_failed"
            )
        if status in {"expired", "disconnected", "suspended"}:
            return ProviderEnvironment(
                id=environment_id, state="unavailable", error="environment_unavailable"
            )
        raise Unknown()

    async def submit_input(self, session_id: str, content: str, run_id: str) -> str:
        before = await self._snapshot(session_id, include_response=False)
        if before.environment is not None and before.environment.state != "connected":
            raise InvalidTransition()
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
        # Artifacts are durable and independent of live workspace/session removal.
        # Preserve the caller's mapping on any uncertain phase, even if another phase succeeds.
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.cleanup_timeout_seconds
        artifact_failure = False
        if hasattr(self.sessions, "artifacts"):
            try:
                async with asyncio.timeout(min(15, self.cleanup_timeout_seconds / 2)):
                    rows = [
                        _dict(row)
                        async for row in self.sessions.artifacts.list(session_id, limit=100)
                    ]
                    for row in rows:
                        try:
                            if row["session_id"] != session_id:
                                raise Unknown()
                            result = _dict(
                                await self.sessions.artifacts.delete(
                                    row["id"], session_id=session_id
                                )
                            )
                            if result["id"] != row["id"] or result["deleted"] is not True:
                                raise Unknown()
                        except Exception as error:
                            if getattr(error, "status_code", None) != 404:
                                artifact_failure = True
            except Exception as error:
                if getattr(error, "status_code", None) != 404:
                    artifact_failure = True
        try:
            async with asyncio.timeout(max(0, deadline - loop.time())):
                for attempt in range(3):
                    try:
                        result = _dict(await self.sessions.delete(session_id))
                        if result["id"] != session_id or result["deleted"] is not True:
                            raise Unknown()
                        break  # Request accepted; physical sandbox destruction is not proven.
                    except Exception as error:
                        status = getattr(error, "status_code", None)
                        if status == 404:
                            break
                        if status != 409 or attempt == 2:
                            raise Unknown() from None
                        await asyncio.sleep(0.1 * (attempt + 1))
        except Exception:
            raise Unknown() from None
        if artifact_failure:
            raise Unknown()

    @staticmethod
    def _artifact(raw: dict, session_id: str) -> ProviderArtifact:
        try:
            path = raw["path"]
            parsed = PurePosixPath(path)
            media = {".json": "application/json", ".md": "text/markdown"}.get(parsed.suffix)
            if (
                raw["session_id"] != session_id
                or not path.startswith("/workspace/outputs/")
                or str(parsed) != path
                or ".." in parsed.parts
                or "\\" in path
                or any(ord(c) < 32 or ord(c) == 127 for c in path)
                or media is None
                or type(raw["size_bytes"]) is not int
            ):
                raise ValueError()
            return ProviderArtifact(
                id=raw["id"],
                session_id=session_id,
                turn_id=raw["turn_id"],
                path=path,
                size=raw["size_bytes"],
                media_type=media,
            )
        except KeyError, TypeError, ValueError:
            raise ArtifactInvalid() from None

    async def list_artifacts(self, session_id: str, turn_id: str) -> tuple[ProviderArtifact, ...]:
        try:
            roots = await self._roots(session_id)
            if not any(t["id"] == turn_id and t["status"] == "completed" for t in roots):
                return ()
            rows = []
            async for raw in self.sessions.artifacts.list(session_id, order="asc", limit=100):
                item = _dict(raw)
                if item["session_id"] != session_id:
                    raise ArtifactInvalid()
                if item["turn_id"] == turn_id:
                    rows.append(self._artifact(item, session_id))
                    if len(rows) > 2 or len({r.id for r in rows}) != len(rows):
                        raise ArtifactInvalid()
            return tuple(rows)
        except ArtifactInvalid:
            raise
        except Exception as error:
            if getattr(error, "status_code", None) in {404, 410}:
                raise ArtifactUnavailable() from None
            raise ArtifactTransient() from None

    async def read_artifact(self, session_id: str, artifact_id: str, *, max_bytes: int) -> bytes:
        if type(max_bytes) is not int or not 0 < max_bytes <= 1048576:
            raise ArtifactInvalid()
        try:
            raw = _dict(await self.sessions.artifacts.retrieve(artifact_id, session_id=session_id))
            artifact = self._artifact(raw, session_id)
            if artifact.id != artifact_id or artifact.size > max_bytes:
                raise ArtifactInvalid()
            content = bytearray()
            async with self.sessions.artifacts.with_streaming_response.content(
                artifact_id, session_id=session_id
            ) as response:
                declared = response.headers.get("content-length")
                if declared is not None and (not declared.isdecimal() or int(declared) > max_bytes):
                    raise ArtifactInvalid()
                async for chunk in response.iter_bytes(chunk_size=min(65536, max_bytes + 1)):
                    if len(content) + len(chunk) > max_bytes:
                        raise ArtifactInvalid()
                    content.extend(chunk)
            if len(content) != artifact.size:
                raise ArtifactInvalid()
            try:
                content.decode("utf-8")
            except UnicodeError:
                raise ArtifactInvalid() from None
            return bytes(content)
        except ArtifactInvalid:
            raise
        except Exception as error:
            if getattr(error, "status_code", None) in {404, 410}:
                raise ArtifactUnavailable() from None
            raise ArtifactTransient() from None


def build_live_provider(
    source_loader: SourceLoader | None = None,
    *,
    api_key: str | None = None,
    model: str | None = None,
    bundle_root: Path | None = None,
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
        AsyncOpenAI(api_key=key, max_retries=0, timeout=20), source_loader, bundle_root=bundle_root
    )
    return provider
