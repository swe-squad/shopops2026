"""Saved provider state, bounded artifact transport and cleanup failure injection."""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.contracts.errors import (
    ArtifactInvalid,
    ArtifactTransient,
    ArtifactUnavailable,
    InvalidTransition,
    ProviderOutcomeUnknown,
)
from app.providers.openai_agents import OpenAIAgentsProvider
from tests.providers.test_events import Page, adapter


class StatusError(Exception):
    def __init__(self, status):
        self.status_code = status


class Artifacts:
    def __init__(self):
        self.rows = []
        self.chunks = [b'{"ok":true}']
        self.reads = 0
        self.closed = False
        self.headers = {}
        self.deleted = []
        self.delete_error = None
        self.content_error = None
        self.with_streaming_response = SimpleNamespace(content=self.content)

    def list(self, session_id, **kwargs):
        return Page(self.rows)

    async def retrieve(self, artifact_id, *, session_id):
        for row in self.rows:
            if row["id"] == artifact_id:
                return row
        raise StatusError(404)

    @asynccontextmanager
    async def content(self, artifact_id, *, session_id):
        if self.content_error:
            raise self.content_error
        try:
            yield self
        finally:
            self.closed = True

    async def iter_bytes(self, chunk_size=None):
        for chunk in self.chunks:
            self.reads += 1
            yield chunk

    async def delete(self, artifact_id, *, session_id):
        self.deleted.append(artifact_id)
        if self.delete_error:
            raise self.delete_error
        return {"id": artifact_id, "deleted": True}


def artifact(**changes):
    return dict(
        {
            "id": "artifact",
            "session_id": "session",
            "turn_id": "turn",
            "environment_id": "env",
            "path": "/workspace/outputs/report.json",
            "size_bytes": 11,
        },
        **changes,
    )


def hosted():
    provider, sessions = adapter()
    sessions.state["environment"] = {"type": "openai_hosted", "id": "env"}
    sessions.state["metadata"] = {"initial_run_id": "run"}
    sessions.turn_rows = [sessions.root]
    environments = SimpleNamespace(
        retrieve=AsyncMock(return_value={"id": "env", "type": "openai_hosted", "status": "pending"})
    )
    provider.client.beta.agents.environments = environments
    sessions.artifacts = Artifacts()
    return provider, sessions, environments


@pytest.mark.parametrize(
    ("status", "state", "error"),
    [
        ("pending", "provisioning", None),
        ("ready", "provisioning", None),
        ("connected", "connected", None),
        ("failed", "failed", "environment_failed"),
        ("expired", "unavailable", "environment_unavailable"),
        ("suspended", "unavailable", "environment_unavailable"),
        ("disconnected", "unavailable", "environment_unavailable"),
    ],
)
def test_inspection_uses_authoritative_environment_state(status, state, error):
    async def exercise():
        provider, sessions, environments = hosted()
        environments.retrieve.return_value["status"] = status
        snapshot = await provider.inspect_session("session")
        assert snapshot.environment.id == "env"
        assert (snapshot.environment.state, snapshot.environment.error) == (state, error)
        assert snapshot.root_status == "running"
        assert snapshot.input_run_id == "run"
        assert not sessions.sent

    asyncio.run(exercise())


def test_provisioning_followed_by_connection_keeps_same_mapping():
    async def exercise():
        provider, sessions, environments = hosted()
        first = await provider.inspect_session("session")
        environments.retrieve.return_value["status"] = "connected"
        second = await provider.inspect_session("session")
        assert first.environment.state == "provisioning"
        assert second.environment.state == "connected"
        assert first.root_turn_id == second.root_turn_id == "turn"
        assert first.environment.id == second.environment.id == "env"
        assert sessions.sent == []

    asyncio.run(exercise())


def test_restart_inspects_state_without_creating_or_resubmitting():
    async def exercise():
        old, sessions, environments = hosted()
        fresh = OpenAIAgentsProvider(old.client)
        sessions.create = AsyncMock(side_effect=AssertionError("must not recreate"))
        snapshot = await fresh.inspect_session("session")
        assert snapshot.input_run_id == "run"
        assert snapshot.environment.state == "provisioning"
        assert not sessions.sent
        environments.retrieve.side_effect = StatusError(404)
        unavailable = await fresh.inspect_session("session")
        assert unavailable.environment.error == "environment_unavailable"
        assert unavailable.environment.id == "env"

    asyncio.run(exercise())


def test_environment_transport_failure_remains_unknown():
    async def exercise():
        provider, sessions, environments = hosted()
        environments.retrieve.side_effect = TimeoutError("private upstream error")
        with pytest.raises(ProviderOutcomeUnknown, match="^provider_outcome_unknown$"):
            await provider.inspect_session("session")
        assert not sessions.sent

    asyncio.run(exercise())


def test_child_and_command_events_are_sanitized_nonterminal_hints():
    async def exercise():
        provider, sessions, _ = hosted()
        sessions.frames = [
            {
                "event_id": "env-ready",
                "session_id": "session",
                "type": "agent.session.environment.connected",
                "environment": {"id": "env", "status": "connected"},
            },
            {
                "event_id": "child-created",
                "type": "agent.session.subagent.created",
                "subagent": {"id": "child", "session_id": "session", "instructions": "private"},
            },
            {
                "event_id": "command-done",
                "session_id": "session",
                "type": "agent.session.turn.item.done",
                "item": {
                    "id": "cmd",
                    "turn_id": "child-turn",
                    "type": "command_execution",
                    "status": "completed",
                    "command": "private command",
                    "output": "private output",
                },
            },
            {
                "event_id": "command-start",
                "session_id": "session",
                "type": "agent.session.turn.item.added",
                "item": {"id": "cmd", "turn_id": "child-turn", "type": "command_execution"},
            },
            {
                "event_id": "child-done",
                "session_id": "session",
                "turn_id": "child-turn",
                "type": "agent.session.turn.completed",
                "turn": {"subagent_id": "child"},
            },
        ]
        sessions.frames.append(sessions.frames[2])  # Replayed event retains its stable ID.
        async with provider.stream_events("session") as stream:
            events = [event async for event in stream]
        assert [e.kind for e in events] == [
            "environment.connected",
            "subagent.started",
            "command.completed",
            "command.started",
            "completed",
            "command.completed",
        ]
        assert all(not e.is_root for e in events)
        assert events[0].turn_id is None and events[1].turn_id is None
        assert events[2].id == events[-1].id
        assert "private" not in "".join(e.model_dump_json() for e in events)
        assert (await provider.inspect_session("session")).root_status == "running"

    asyncio.run(exercise())


def test_artifacts_filter_owned_completed_root_and_infer_media_type():
    async def exercise():
        provider, sessions, _ = hosted()
        sessions.root["status"] = "completed"
        sessions.artifacts.rows = [
            artifact(),
            artifact(id="child-file", turn_id="child"),
            artifact(id="old-file", turn_id="old"),
            artifact(id="notes", path="/workspace/outputs/notes.md"),
        ]
        rows = await provider.list_artifacts("session", "turn")
        assert [r.id for r in rows] == ["artifact", "notes"]
        assert [r.media_type for r in rows] == ["application/json", "text/markdown"]
        assert all(r.session_id == "session" and r.turn_id == "turn" for r in rows)
        assert await provider.list_artifacts("session", "child") == ()
        sessions.root["status"] = "in_progress"
        assert await provider.list_artifacts("session", "turn") == ()

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "change",
    [
        {"session_id": "foreign"},
        {"path": "/workspace/outputs/../private.json"},
        {"path": "/workspace/outputs/report.html"},
        {"path": "/workspace/outputs//report.json"},
        {"path": "/workspace/outputs/report.json\r\nInjected: header"},
        {"size_bytes": 1048577},
        {"size_bytes": -1},
    ],
)
def test_artifacts_reject_invalid_metadata(change):
    async def exercise():
        provider, sessions, _ = hosted()
        sessions.root["status"] = "completed"
        sessions.artifacts.rows = [artifact(**change)]
        with pytest.raises(ArtifactInvalid):
            await provider.list_artifacts("session", "turn")

    asyncio.run(exercise())


def test_read_enforces_actual_byte_limit_before_consuming_rest():
    async def exercise():
        provider, sessions, _ = hosted()
        sessions.artifacts.rows = [artifact(size_bytes=1)]  # Deliberately inaccurate metadata.
        sessions.artifacts.chunks = [b"1234", b"5678", b"never read"]
        with pytest.raises(ArtifactInvalid):
            await provider.read_artifact("session", "artifact", max_bytes=5)
        assert sessions.artifacts.reads == 2
        assert sessions.artifacts.closed

    asyncio.run(exercise())


@pytest.mark.parametrize("size", [0, -1, 1048577])
def test_read_rejects_invalid_limit_without_io(size):
    async def exercise():
        provider, sessions, _ = hosted()
        with pytest.raises(ArtifactInvalid):
            await provider.read_artifact("session", "artifact", max_bytes=size)
        assert sessions.artifacts.reads == 0

    asyncio.run(exercise())


def test_read_valid_utf8_and_error_classes():
    async def exercise():
        provider, sessions, _ = hosted()
        sessions.artifacts.rows = [artifact()]
        assert await provider.read_artifact("session", "artifact", max_bytes=100) == b'{"ok":true}'
        for status, error in [
            (404, ArtifactUnavailable),
            (410, ArtifactUnavailable),
            (503, ArtifactTransient),
        ]:
            sessions.artifacts.content_error = StatusError(status)
            with pytest.raises(error):
                await provider.read_artifact("session", "artifact", max_bytes=100)
        sessions.artifacts.content_error = None
        sessions.artifacts.chunks = [b"\xff"]
        with pytest.raises(ArtifactInvalid):
            await provider.read_artifact("session", "artifact", max_bytes=100)

    asyncio.run(exercise())


@pytest.mark.parametrize("status", ["pending", "failed", "expired"])
def test_follow_up_never_resubmits_to_unusable_environment(status):
    async def exercise():
        provider, sessions, environments = hosted()
        sessions.root["status"] = "completed"
        environments.retrieve.return_value["status"] = status
        with pytest.raises(InvalidTransition):
            await provider.submit_input("session", "follow-up", "run-2")
        assert sessions.sent == []

    asyncio.run(exercise())


def test_read_checks_metadata_identity_size_and_content_length():
    async def exercise():
        provider, sessions, _ = hosted()
        sessions.artifacts.rows = [artifact(size_bytes=1)]
        with pytest.raises(ArtifactInvalid):
            await provider.read_artifact("session", "artifact", max_bytes=100)
        sessions.artifacts.rows = [artifact()]
        sessions.artifacts.headers = {"content-length": "101"}
        sessions.artifacts.reads = 0
        with pytest.raises(ArtifactInvalid):
            await provider.read_artifact("session", "artifact", max_bytes=100)
        assert sessions.artifacts.reads == 0
        sessions.artifacts.rows = [artifact(session_id="foreign")]
        with pytest.raises(ArtifactInvalid):
            await provider.read_artifact("session", "artifact", max_bytes=100)

    asyncio.run(exercise())


def test_cleanup_rejects_unconfirmed_delete_responses():
    async def exercise():
        provider, sessions, _ = hosted()
        sessions.artifacts.rows = [artifact()]
        sessions.artifacts.delete = AsyncMock(return_value={"id": "artifact", "deleted": False})
        sessions.delete = AsyncMock(return_value={"id": "session", "deleted": True})
        with pytest.raises(ProviderOutcomeUnknown):
            await provider.delete_session("session")
        assert sessions.delete.call_count == 1
        sessions.artifacts.rows = []
        sessions.delete = AsyncMock(return_value={"id": "foreign", "deleted": True})
        with pytest.raises(ProviderOutcomeUnknown):
            await provider.delete_session("session")

    asyncio.run(exercise())


def test_cleanup_timeout_still_attempts_session_and_retains_uncertainty():
    async def exercise():
        provider, sessions, _ = hosted()
        provider.cleanup_timeout_seconds = 0.02

        async def stalled_listing():
            await asyncio.sleep(5)
            yield artifact()

        sessions.artifacts.list = lambda *args, **kwargs: stalled_listing()
        sessions.delete = AsyncMock(return_value={"id": "session", "deleted": True})
        with pytest.raises(ProviderOutcomeUnknown):
            await provider.delete_session("session")
        assert sessions.delete.call_count == 1

    asyncio.run(exercise())


def test_cleanup_attempts_all_artifacts_and_session_despite_artifact_failure():
    async def exercise():
        provider, sessions, _ = hosted()
        sessions.artifacts.rows = [artifact(), artifact(id="second", turn_id="child")]
        sessions.artifacts.delete_error = StatusError(503)
        with pytest.raises(ProviderOutcomeUnknown):
            await provider.delete_session("session")
        assert sessions.artifacts.deleted == ["artifact", "second"]
        assert sessions.deleted

    asyncio.run(exercise())


def test_delete_known_conflicts_are_bounded_and_404_is_absent():
    async def exercise():
        provider, sessions, _ = hosted()
        sessions.delete = AsyncMock(
            side_effect=[StatusError(409), StatusError(409), {"id": "session", "deleted": True}]
        )
        await provider.delete_session("session")
        assert sessions.delete.call_count == 3
        sessions.delete = AsyncMock(side_effect=StatusError(409))
        with pytest.raises(ProviderOutcomeUnknown):
            await provider.delete_session("session")
        assert sessions.delete.call_count == 3
        sessions.delete = AsyncMock(side_effect=StatusError(404))
        await provider.delete_session("session")
        assert sessions.delete.call_count == 1
        sessions.delete = AsyncMock(side_effect=TimeoutError("unknown outcome"))
        with pytest.raises(ProviderOutcomeUnknown):
            await provider.delete_session("session")
        assert sessions.delete.call_count == 1

    asyncio.run(exercise())
