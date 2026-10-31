"""Offline API acceptance with synthetic provider files, never hosted execution evidence."""

import hashlib
import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.contracts.errors import ArtifactUnavailable
from app.contracts.models import ApplicationResponse, Source
from app.contracts.provider import ProviderEvent
from app.contracts.runtime import ProviderArtifact, ProviderEnvironment
from app.contracts.tools import PendingToolCall, ToolDefinition, ToolResult
from app.main import create_app
from app.providers.fake import FakeProvider, Scenario
from tests.integration.test_runtime import environment

REPORT = json.loads(Path("fixtures/runtime/report.json").read_text())


class FixtureTools:
    """Deterministic boundary data; real MCP transport remains covered by baseline tests."""

    def definitions(self, config):
        return tuple(
            ToolDefinition(name=name, description="Synthetic acceptance", input_schema={})
            for name in ("get_return_metrics", "search_knowledge")
        )

    async def execute(self, scope, conversation_id, config, call):
        index = 0 if call.name == "get_return_metrics" else 1
        return ToolResult(
            data=REPORT["metrics"] if index == 0 else {"excerpt": "Synthetic sizing policy"},
            sources=(Source.model_validate(REPORT["sources"][index]),),
        )


class HostedFiles(FakeProvider):
    def __init__(self, *, kind="answer", failure=None, delayed=False):
        response = ApplicationResponse(kind=kind, text="Dữ liệu tổng hợp thử nghiệm.")
        super().__init__(
            [
                Scenario(tool_name="get_return_metrics")
                if kind == "answer"
                else Scenario(response=response),
                Scenario(
                    response=ApplicationResponse(kind="answer", text="Tăng 10 điểm phần trăm.")
                ),
            ]
        )
        self.failure = failure
        self.delayed = delayed
        self.payload = json.dumps(REPORT, ensure_ascii=False).encode()
        self.report_turns = set()
        self.reads = 0
        self.saved_responses = {}

    async def create_session(self, config, correlation_id, *, initial_input=None):
        result = await super().create_session(config, correlation_id, initial_input=initial_input)
        session = self._session(result.id)
        state = {
            "setup": "failed",
            "setup_timeout": "provisioning",
            "environment_expired": "unavailable",
        }.get(self.failure, "connected")
        env = ProviderEnvironment(id="env-" + result.id, state=state)
        session.snapshot = session.snapshot.model_copy(update={"environment": env})
        return result.model_copy(update={"environment": env})

    async def submit_input(self, session_id, content, run_id):
        environment = self._session(session_id).snapshot.environment
        turn = await super().submit_input(session_id, content, run_id)
        if environment is not None:
            self._session(session_id).snapshot = self._session(session_id).snapshot.model_copy(
                update={"environment": environment}
            )
        if "report.json" in content:
            self.report_turns.add(turn)
        return turn

    async def submit_tool_result(self, call, result):
        session = self._session(call.session_id)
        session.deliveries[(call.turn_id, call.call_id)] = (call, result)
        if call.name == "get_return_metrics":
            pending = PendingToolCall(
                session_id=call.session_id,
                turn_id=call.turn_id,
                call_id="policy-" + call.turn_id,
                name="search_knowledge",
                arguments={"query": "sizing"},
            )
            session.snapshot = session.snapshot.model_copy(update={"pending_calls": (pending,)})
            return
        sources = tuple(s for _, r in session.deliveries.values() for s in r.sources)
        response = ApplicationResponse(
            kind="answer", text="Tăng 10 điểm phần trăm.", sources=sources
        )
        if self.delayed:
            self.saved_responses[call.session_id] = response
            session.snapshot = session.snapshot.model_copy(
                update={"root_status": "running", "pending_calls": ()}
            )
            for index in range(2):
                event = ProviderEvent(
                    id=f"child-event-{index}",
                    session_id=call.session_id,
                    turn_id=f"child-turn-{index}",
                    kind="subagent.completed",
                    is_root=False,
                )
                for queue in session.queues:
                    queue.put_nowait(event)
                    queue.put_nowait(None)  # Stream loss after child completion.
        else:
            self._finish(session, response)

    async def list_artifacts(self, session_id, turn_id):
        response = self._session(session_id).snapshot.response
        if turn_id not in self.report_turns or response is None or response.kind != "answer":
            return ()
        if self.failure == "missing":
            return ()
        return (
            ProviderArtifact(
                id="file-" + turn_id,
                session_id=session_id,
                turn_id="foreign-root" if self.failure == "foreign_root" else turn_id,
                path="/workspace/outputs/report.json",
                size=len(self.payload) + (1 if self.failure == "size" else 0),
                media_type="application/json",
            ),
        )

    async def read_artifact(self, session_id, artifact_id, *, max_bytes):
        self.reads += 1
        if self.failure == "expired":
            raise ArtifactUnavailable()
        return self.payload


@pytest.fixture
def api(tmp_path):
    from app.contracts.runtime import RuntimeProfile

    registry = json.loads(Path("config/registry.json").read_text())
    manifest = json.loads(Path("runtime-bundles/shopops-hosted-v1/manifest.json").read_text())
    profile = RuntimeProfile(
        profile_id="shopops-hosted-v1",
        environment_type="openai_hosted",
        bundle_id=manifest["bundle_id"],
        bundle_version=manifest["bundle_version"],
        bundle_sha256=manifest["bundle_sha256"],
        container_size="small",
        multi_agent_enabled=True,
        max_concurrent_subagents=2,
    )
    registry["revisions"] = [
        registry["revisions"][0]
        | {
            "revision": "hosted-offline",
            "runtime_profile": profile.model_dump(),
        }
    ]
    registry["revisions"].append(registry["revisions"][0] | {"revision": "hosted-smoke-v1"})
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(registry))

    def build(provider):
        app = create_app(
            settings=Settings.from_env(environment(tmp_path) | {"CONFIG_PATH": str(path)}),
            provider=provider,
            bridge=FixtureTools(),
        )
        return app, TestClient(app, headers={"Authorization": "Bearer local-alice"})

    return build


def conversation(client, key="first"):
    provision = client.post(
        "/api/v1/shops/shop-a/orchestrator",
        json={
            "template_id": "shopops",
            "config_revision": "hosted-offline",
        },
    )
    assert provision.status_code in {200, 201}
    result = client.post(
        "/api/v1/shops/shop-a/conversations",
        json={
            "orchestrator_id": provision.json()["orchestrator_id"],
            "client_conversation_id": key,
        },
    )
    assert result.status_code == 201
    return result.json()["conversation_id"]


def submit(client, cid, *, mode="report", key="report"):
    result = client.post(
        f"/api/v1/conversations/{cid}/messages",
        json={
            "client_message_id": key,
            "content": "SKU-A 2026-10-19 đến 2026-10-25 và chính sách sizing",
            "output_mode": mode,
        },
    )
    assert result.status_code == 202
    return result.json()["run_id"]


def terminal(client, rid):
    deadline = time.monotonic() + 6
    while time.monotonic() < deadline:
        result = client.get(f"/api/v1/runs/{rid}")
        assert result.status_code == 200
        run = result.json()
        if run["status"] in {"completed", "failed", "cancelled"}:
            return run
        time.sleep(0.01)
    raise AssertionError("offline_run_did_not_finish")


def test_report_download_followup_isolation_and_restart(api):
    provider = HostedFiles()
    app, client = api(provider)
    with client:
        cid = conversation(client)
        rid = submit(client, cid)
        run = terminal(client, rid)
        assert run["status"] == "completed"
        assert run["response"]["sources"] == REPORT["sources"]
        listing = client.get(f"/api/v1/runs/{rid}/artifacts").json()
        artifact = listing["items"][0]
        url = f"/api/v1/artifacts/{artifact['id']}/content"
        download = client.get(url)
        assert download.status_code == 200
        assert download.json() == REPORT
        assert hashlib.sha256(download.content).hexdigest() == artifact["sha256"]
        reads = provider.reads
        for token in ("local-bob", "local-carol"):
            assert client.get(url, headers={"Authorization": f"Bearer {token}"}).status_code == 404
            assert (
                client.get(
                    f"/api/v1/runs/{rid}/artifacts", headers={"Authorization": f"Bearer {token}"}
                ).status_code
                == 404
            )
        assert provider.reads == reads
        followup = submit(client, cid, mode="text", key="followup")
        assert terminal(client, followup)["status"] == "completed"
        assert client.get(f"/api/v1/runs/{followup}/artifacts").json()["items"] == []
        assert len(provider.sessions) == 1
        assert len(client.get(f"/api/v1/conversations/{cid}/history").json()["items"]) == 4
        # Replay returns the existing receipt without another turn.
        assert submit(client, cid) == rid
        cid2 = conversation(client, "second")
        assert terminal(client, submit(client, cid2))["status"] == "completed"
        assert len(provider.sessions) == 2
        assert len({s.snapshot.environment.id for s in provider.sessions.values()}) == 2
    # Recreate the application, preserving DB/profile/artifact metadata.
    _, reopened = api(provider)
    with reopened:
        assert reopened.get(url).content == download.content
        assert reopened.get(f"/api/v1/runs/{rid}").json()["status"] == "completed"
        provider.failure = "expired"
        assert reopened.get(url).status_code == 410
        assert reopened.get(f"/api/v1/runs/{rid}").json()["status"] == "completed"


@pytest.mark.parametrize("failure", ["missing", "size", "foreign_root"])
def test_invalid_root_artifact_fails_report(api, failure):
    _, client = api(HostedFiles(failure=failure))
    with client:
        rid = submit(client, conversation(client))
        result = terminal(client, rid)
        assert result["status"] == "failed"
        assert result["error"] == "artifact_invalid"
        assert client.get(f"/api/v1/runs/{rid}/artifacts").json()["items"] == []


@pytest.mark.parametrize("kind", ["clarification", "cannot_answer"])
def test_report_without_information_needs_no_fabricated_artifact(api, kind):
    provider = HostedFiles(kind=kind)
    _, client = api(provider)
    with client:
        rid = submit(client, conversation(client))
        result = terminal(client, rid)
        assert result["status"] == "completed"
        assert result["response"]["kind"] == kind
        assert result["response"]["sources"] == []
        assert client.get(f"/api/v1/runs/{rid}/artifacts").json()["items"] == []
        assert provider.reads == 0


def test_child_completion_and_lost_stream_wait_for_saved_root(api):
    provider = HostedFiles(delayed=True)
    _, client = api(provider)
    with client:
        rid = submit(client, conversation(client))
        deadline = time.monotonic() + 5
        while not provider.saved_responses and time.monotonic() < deadline:
            time.sleep(0.01)
        assert provider.saved_responses
        assert client.get(f"/api/v1/runs/{rid}").json()["status"] not in {"completed", "failed"}
        assert client.get(f"/api/v1/runs/{rid}/artifacts").json()["items"] == []

        async def finish():
            sid, response = next(iter(provider.saved_responses.items()))
            provider._finish(provider._session(sid), response)

        client.portal.call(finish)
        assert terminal(client, rid)["status"] == "completed"
        assert len(provider.sessions) == 1
        assert next(iter(provider.sessions.values())).turn_count == 1


@pytest.mark.parametrize(
    "failure,code",
    [
        ("setup", "environment_failed"),
        ("setup_timeout", "environment_timeout"),
        ("environment_expired", "environment_unavailable"),
    ],
)
def test_setup_failure_keeps_environment_and_blocks_followup(api, failure, code):
    provider = HostedFiles(failure=failure)
    app, client = api(provider)
    with client:
        if failure == "setup_timeout":
            from datetime import timedelta

            from app.storage.repositories import utcnow

            app.state.worker.clock = lambda: utcnow() + timedelta(seconds=61)
        cid = conversation(client)
        rid = submit(client, cid)
        result = terminal(client, rid)
        assert result["status"] == "failed"

        async def saved():
            conversation, _ = await app.state.repository.execution_context(rid)
            return await app.state.repository.get_run(conversation.scope, rid)

        assert client.portal.call(saved).error == code
        response = client.post(
            f"/api/v1/conversations/{cid}/messages",
            json={
                "client_message_id": "new",
                "content": "Thử lại",
                "output_mode": "text",
            },
        )
        assert response.status_code == 409
        assert len(provider.sessions) == 1


@pytest.mark.parametrize(
    "code", ["environment_failed", "environment_timeout", "environment_unavailable"]
)
def test_hosted_setup_error_remains_actionable_in_public_api(code):
    from app.api.runs import public_error

    assert public_error(code) == code


def test_wrong_bundle_fails_before_any_provider_mutation():
    from app.agents.runtime_bundle import build_runtime_bundle
    from app.contracts.errors import ConfigurationConflict
    from app.contracts.runtime import RuntimeProfile

    profile = RuntimeProfile(
        profile_id="shopops-hosted-v1",
        environment_type="openai_hosted",
        bundle_id="shopops-hosted-v1",
        bundle_version="1.0.0",
        bundle_sha256="0" * 64,
        container_size="small",
        multi_agent_enabled=True,
        max_concurrent_subagents=2,
    )
    with pytest.raises(ConfigurationConflict):
        build_runtime_bundle(profile)


def test_download_revalidates_digest_without_rewriting_history(api):
    provider = HostedFiles()
    _, client = api(provider)
    with client:
        rid = submit(client, conversation(client))
        assert terminal(client, rid)["status"] == "completed"
        artifact = client.get(f"/api/v1/runs/{rid}/artifacts").json()["items"][0]
        provider.payload = provider.payload.replace(b'"returns": 15', b'"returns": 16')
        assert client.get(f"/api/v1/artifacts/{artifact['id']}/content").status_code == 502
        assert client.get(f"/api/v1/runs/{rid}").json()["status"] == "completed"


def saved_execution():
    """SDK-shaped saved records; independent synthetic proof oracle."""
    import shlex

    from scripts.hosted_smoke import ROOT, bundle_execution_code

    commands = [
        "cat /plugin/skills/returns-analysis/SKILL.md",
        "cat /plugin/skills/knowledge-review/SKILL.md",
        shlex.join(
            [
                "python",
                "-I",
                "-B",
                "-c",
                bundle_execution_code(),
                "/plugin",
                "/workspace/input.json",
                "/workspace/outputs/report.json",
            ]
        ),
    ]
    return {
        "knowledge_references": frozenset({"knowledge:returns-v1:1:sizing#synthetic"}),
        "session": {
            "id": "s",
            "agent": {"id": "agent-root"},
            "environment": {
                "type": "openai_hosted",
                "id": "env",
                "network": {"access": "disabled"},
            },
        },
        "environment": {"id": "env", "type": "openai_hosted", "status": "connected"},
        "root_turn_id": "root",
        "turns": [{"id": "root", "session_id": "s", "subagent_id": None, "status": "completed"}],
        "items": [
            {
                "id": f"cmd-{i}",
                "turn_id": "root",
                "type": "command_execution",
                "command": cmd,
                "status": "completed",
                "exit_code": 0,
                "output": (
                    ROOT
                    / "runtime-bundles/shopops-hosted-v1/shopops-analysis"
                    / (
                        "skills/returns-analysis/SKILL.md"
                        if i == 0
                        else "skills/knowledge-review/SKILL.md"
                    )
                ).read_text()
                if i < 2
                else "shopops-bundle-helper-verified\n",
            }
            for i, cmd in enumerate(commands)
        ],
        "children": [
            {
                "id": f"child-{i}",
                "session_id": "s",
                "parent_agent_id": "agent-root",
                "instructions": [{"type": "output_text", "text": role}],
                "turns": [
                    {
                        "id": f"ct-{i}",
                        "session_id": "s",
                        "subagent_id": f"child-{i}",
                        "status": "completed",
                    }
                ],
                "items": [
                    {
                        "id": f"result-{i}",
                        "turn_id": f"ct-{i}",
                        "type": "message",
                        "role": "assistant",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "5% 15% 10 points"
                                if i == 0
                                else "knowledge:returns-v1:1:sizing#synthetic",
                            }
                        ],
                    }
                ],
            }
            for i, role in enumerate(("data-analyst", "knowledge-analyst"))
        ],
    }


def test_saved_proof_accepts_real_shaped_items_and_rejects_prompt_claims():
    from scripts.hosted_smoke import EvidenceInvalid, verify_execution

    proof = saved_execution()
    summary = verify_execution(**proof, require_probe=False)
    assert summary["completed_children"] == 2
    assert summary["skill_reads_verified"] and summary["helper_execution_verified"]
    assert "command" not in json.dumps(summary)
    proof["items"] = [
        {
            "type": "message",
            "role": "assistant",
            "content": [
                {
                    "type": "output_text",
                    "text": "I read both skills, ran Python and created two specialists.",
                },
            ],
        }
    ]
    with pytest.raises(EvidenceInvalid):
        verify_execution(**proof, require_probe=False)


@pytest.mark.parametrize(
    "damage",
    [
        "same_child",
        "unfinished_root",
        "wrong_root",
        "failed_command",
        "echo",
        "missing_probe",
        "wrong_session",
        "heredoc",
        "compound_helper",
        "two_roles_one_child",
        "fake_python",
        "fake_knowledge",
    ],
)
@pytest.mark.parametrize("wrapped", [False, True])
def test_saved_proof_rejects_incomplete_or_uncorrelated_evidence(damage, wrapped):
    from scripts.hosted_smoke import EvidenceInvalid, verify_execution

    proof = saved_execution()
    if damage == "same_child":
        proof["children"][1]["id"] = "child-0"
    elif damage == "unfinished_root":
        proof["turns"][0]["status"] = "in_progress"
    elif damage == "wrong_root":
        proof["items"][2]["turn_id"] = "unrelated"
    elif damage == "failed_command":
        proof["items"][2]["exit_code"] = 1
    elif damage == "echo":
        proof["items"][0]["command"] = "echo cat /plugin/skills/returns-analysis/SKILL.md"
    elif damage == "wrong_session":
        proof["children"][0]["session_id"] = "foreign"
    elif damage == "heredoc":
        proof["items"][0]["command"] = "cat <<EOF\n/plugin/skills/returns-analysis/SKILL.md\nEOF"
    elif damage == "compound_helper":
        proof["items"][2]["command"] = proof["items"][2]["command"].replace(
            "/workspace/input.json", "/workspace/input.json;true"
        )
    elif damage == "two_roles_one_child":
        proof["children"][0]["instructions"][0]["text"] = "data-analyst knowledge-analyst"
        proof["children"][0]["items"][0]["content"][0]["text"] += (
            " knowledge:returns-v1:1:sizing#synthetic"
        )
        proof["children"][1]["instructions"][0]["text"] = "unrelated"
    elif damage == "fake_python":
        proof["items"][2]["command"] = proof["items"][2]["command"].replace(
            "python ", "/workspace/fake/python "
        )
    elif damage == "fake_knowledge":
        proof["children"][1]["items"][0]["content"][0]["text"] = (
            "knowledge:returns-v1:1:nonexistent"
        )
    if wrapped:
        import shlex

        for item in proof["items"]:
            item["command"] = shlex.join(["/bin/bash", "-lc", item["command"]])
    with pytest.raises(EvidenceInvalid):
        verify_execution(**proof, require_probe=damage == "missing_probe")


@pytest.mark.parametrize("outcome", ["success", "409", "404", "unknown", "artifact_failure"])
def test_hosted_cleanup_preserves_uncertainty_and_attempts_other_resources(outcome):
    import asyncio
    from types import SimpleNamespace

    from scripts.hosted_smoke import cleanup_remote

    class RemoteError(Exception):
        def __init__(self, status=None):
            self.status_code = status

    class Remote:
        def __init__(self):
            self.remaining = {"first", "second"}
            self.attempts = {}
            self.artifacts = self

        def list(self, sid, **kwargs):
            async def generate():
                yield {"id": "file-" + sid}

            return generate()

        async def delete(self, ident, *, session_id=None):
            if session_id is not None:
                if outcome == "artifact_failure" and session_id == "first":
                    raise RemoteError()
                return {"id": ident, "deleted": True}
            self.attempts[ident] = self.attempts.get(ident, 0) + 1
            if ident == "first":
                if outcome == "409":
                    raise RemoteError(409)
                if outcome == "unknown":
                    raise RemoteError()
                if outcome == "404":
                    self.remaining.discard(ident)
                    raise RemoteError(404)
            self.remaining.discard(ident)

        async def retrieve(self, sid):
            if sid not in self.remaining:
                raise RemoteError(404)
            return SimpleNamespace(id=sid)

    remote = Remote()
    result = asyncio.run(cleanup_remote(remote, {"first", "second"}))
    assert "second" not in remote.remaining
    assert result["cleanup"] == (outcome in {"success", "404"})
    assert result["confirmed_session_removals"] == (1 if outcome in {"409", "unknown"} else 2)
    assert result["physical_sandbox_destruction_confirmed"] is False
    if outcome == "409":
        assert remote.attempts["first"] == 3


@pytest.mark.parametrize("failure", ["worker_stop", "recovery_write"])
def test_worker_shutdown_failure_still_attempts_all_remote_cleanup(tmp_path, monkeypatch, failure):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from scripts.hosted_smoke import _cleanup_app

    class Absent(Exception):
        status_code = 404

    async def empty(*args, **kwargs):
        if False:
            yield None

    removed = set()

    async def delete(sid):
        removed.add(sid)

    sessions = SimpleNamespace(
        list=empty,
        artifacts=SimpleNamespace(list=empty),
        delete=delete,
        retrieve=AsyncMock(side_effect=Absent()),
    )
    provider = SimpleNamespace(
        sessions=sessions,
        created_sessions=["first", "second"],
        inspect_session=AsyncMock(side_effect=RuntimeError()),
    )
    app = SimpleNamespace(
        state=SimpleNamespace(
            provider=provider,
            worker=SimpleNamespace(stop=AsyncMock(side_effect=RuntimeError())),
        )
    )
    if failure == "recovery_write":
        app.state.worker = None
        original = Path.write_text

        def write(path, *args, **kwargs):
            if path.name == "remote-recovery.json":
                raise OSError("synthetic disk full")
            return original(path, *args, **kwargs)

        monkeypatch.setattr(Path, "write_text", write)
    result = asyncio.run(_cleanup_app(app, [], [], tmp_path))
    assert removed == {"first", "second"}
    assert not result["cleanup"]
    assert (tmp_path / "remote-recovery.json").exists() == (failure != "recovery_write")


def test_server_shutdown_error_cannot_pass_or_delete_recovery(tmp_path, monkeypatch):
    import asyncio
    import shutil
    from contextlib import contextmanager
    from types import SimpleNamespace

    from scripts import hosted_smoke, live_smoke

    source = hosted_smoke.ROOT
    (tmp_path / "config").mkdir()
    shutil.copyfile(source / "config/registry.json", tmp_path / "config/registry.json")
    monkeypatch.setattr(hosted_smoke, "ROOT", tmp_path)

    @contextmanager
    def broken_shutdown(*args):
        yield object()
        raise RuntimeError("smoke_shutdown_failed")

    monkeypatch.setattr(live_smoke, "serve", broken_shutdown)
    monkeypatch.setattr("app.main.create_app", lambda **kwargs: object())
    monkeypatch.setattr(hosted_smoke, "_workflow", lambda *args: None)

    async def cleaned(*args):
        return {"cleanup": True, "local_cleanup": True}

    monkeypatch.setattr(hosted_smoke, "_cleanup_app", cleaned)

    def submit(coro, loop):
        return SimpleNamespace(result=lambda timeout: asyncio.run(coro))

    monkeypatch.setattr(asyncio, "run_coroutine_threadsafe", submit)
    profile = SimpleNamespace(
        bundle_version="synthetic", bundle_sha256="a" * 64, model_dump=lambda: {}
    )
    result = hosted_smoke._execute(profile, "synthetic-key", "synthetic-model")
    assert result["status"] == "failed"
    assert result["error"] == "hosted_startup_or_shutdown_failed"
    assert Path(result["recovery_directory"]).is_dir()


def test_verified_bundle_bytes_are_executed_and_tampering_stops_before_output(tmp_path):
    import shutil
    import subprocess
    import sys

    from scripts.hosted_smoke import ROOT, bundle_execution_code

    plugin = tmp_path / "plugin"
    shutil.copytree(ROOT / "runtime-bundles/shopops-hosted-v1/shopops-analysis", plugin)
    source, output = tmp_path / "input.json", tmp_path / "report.json"
    source.write_text(
        json.dumps({k: REPORT[k] for k in ("metrics", "knowledge_findings", "sources")})
    )
    command = [
        sys.executable,
        "-I",
        "-B",
        "-c",
        bundle_execution_code(),
        str(plugin),
        str(source),
        str(output),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "shopops-bundle-helper-verified"
    assert json.loads(output.read_text()) == REPORT
    output.unlink()
    helper = plugin / "skills/returns-analysis/scripts/summarize_returns.py"
    helper.write_text(helper.read_text() + "\n# unapproved mutation\n")
    result = subprocess.run(command, capture_output=True, text=True, timeout=10)
    assert result.returncode != 0
    assert not output.exists()


def test_cleanup_discovers_run_when_application_receipt_was_lost(tmp_path):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from scripts.hosted_smoke import _cleanup_app

    removed = set()

    class Absent(Exception):
        status_code = 404

    class Remote:
        def __init__(self):
            self.artifacts = self

        async def list(self, *args, **kwargs):
            if not args:
                yield {"id": "unknown-create", "metadata": {"initial_run_id": "lost-receipt"}}

        async def delete(self, sid):
            removed.add(sid)

        async def retrieve(self, sid):
            raise Absent()

    repo = SimpleNamespace(
        pending_runs=AsyncMock(
            return_value=(SimpleNamespace(id="lost-receipt", conversation_id="c"),)
        ),
        execution_context=AsyncMock(return_value=(SimpleNamespace(provider_session_id=None), None)),
        delete_conversation=AsyncMock(),
    )
    provider = SimpleNamespace(
        sessions=Remote(),
        created_sessions=[],
        inspect_session=AsyncMock(return_value=SimpleNamespace(root_status="failed")),
    )
    app = SimpleNamespace(state=SimpleNamespace(provider=provider, worker=None, repository=repo))
    result = asyncio.run(_cleanup_app(app, ["c"], [], tmp_path))
    assert removed == {"unknown-create"}
    assert result["cleanup"] and result["local_cleanup"]
    assert json.loads((tmp_path / "remote-recovery.json").read_text())["run_ids"] == [
        "lost-receipt"
    ]


def test_boundary_probe_requires_exact_saved_execution_and_sanitized_marker():
    import shlex

    from scripts.hosted_smoke import PROBE, EvidenceInvalid, verify_execution

    proof = saved_execution()
    item = {
        "id": "probe",
        "type": "command_execution",
        "turn_id": "root",
        "status": "completed",
        "exit_code": 0,
        "command": shlex.join(["python", "-I", "-B", "-c", PROBE]),
        "output": "hosted-boundary-denied\n",
    }
    proof["items"].append(item)
    assert verify_execution(**proof)["boundary_probe_verified"]
    item["command"] = "echo hosted-boundary-denied"
    with pytest.raises(EvidenceInvalid):
        verify_execution(**proof)


def test_smoke_drives_actual_application_api_with_synthetic_provider(api, monkeypatch):
    import asyncio

    from scripts import hosted_smoke

    class TwoConversations(HostedFiles):
        async def create_session(self, config, correlation_id, *, initial_input=None):
            if self.sessions:
                self.scenarios = (
                    Scenario(
                        response=ApplicationResponse(
                            kind="clarification",
                            text="Bạn cần xem SKU nào và ngày nào?",
                        )
                    ),
                )
            return await super().create_session(config, correlation_id, initial_input=initial_input)

    async def synthetic_proof(*args, **kwargs):
        return hosted_smoke.verify_execution(**saved_execution(), require_probe=False)

    monkeypatch.setattr(hosted_smoke, "collect_execution", synthetic_proof)
    app, client = api(TwoConversations())
    with client:
        loop = client.portal.call(asyncio.get_running_loop)
        conversations, run_ids, result = [], [], {}
        hosted_smoke._workflow(client, app, loop, conversations, run_ids, result)
        assert result["completed_turns"] == 3
        assert result["execution_verified"] and result["isolation_verified"]
        assert len(conversations) == 2 and len(run_ids) == 3
        # This is transport/lifecycle evidence only. The saved records above are synthetic.
        assert not result["boundary_probe_verified"]


@pytest.mark.parametrize("ack", ["not_deleted", "wrong_id", "missing"])
def test_hosted_cleanup_requires_artifact_deletion_acknowledgement(ack):
    import asyncio

    from scripts.hosted_smoke import cleanup_remote

    class Absent(Exception):
        status_code = 404

    class Remote:
        def __init__(self):
            self.artifacts = self
            self.sessions_removed = set()
            self.artifacts_attempted = set()

        def list(self, sid, **kwargs):
            async def rows():
                yield {"id": "file-" + sid, "session_id": sid}

            return rows()

        async def delete(self, ident, *, session_id=None):
            if session_id is not None:
                self.artifacts_attempted.add(ident)
                if session_id == "first":
                    if ack == "missing":
                        return {}
                    return {
                        "id": "other" if ack == "wrong_id" else ident,
                        "deleted": ack != "not_deleted",
                    }
                return {"id": ident, "deleted": True}
            self.sessions_removed.add(ident)
            return {"id": ident, "deleted": True}

        async def retrieve(self, sid):
            raise Absent()

    remote = Remote()
    result = asyncio.run(cleanup_remote(remote, {"first", "second"}))
    assert remote.sessions_removed == {"first", "second"}
    assert remote.artifacts_attempted == {"file-first", "file-second"}
    assert result["confirmed_session_removals"] == 2
    assert result["cleanup"] is False


@pytest.mark.parametrize("error", ["environment_timeout", "private diagnostic payload"])
def test_smoke_failure_diagnostics_are_safe_and_identify_stage(error):
    from types import SimpleNamespace

    from scripts.hosted_smoke import EvidenceInvalid, _workflow

    responses = iter(
        [
            {"orchestrator_id": "private-orchestrator"},
            {"conversation_id": "private-conversation"},
            {"run_id": "private-run"},
            {"status": "failed", "error": error, "response": "private model output"},
        ]
    )

    class Client:
        def request(self, *args, **kwargs):
            payload = next(responses)
            return SimpleNamespace(raise_for_status=lambda: None, json=lambda: payload)

    evidence = {}
    with pytest.raises(EvidenceInvalid):
        _workflow(Client(), None, None, [], [], evidence)
    assert evidence["stage"] == "first_report"
    assert evidence["last_run_status"] == "failed"
    assert evidence["last_run_error"] == (
        error if error == "environment_timeout" else "internal_error"
    )
    assert "private" not in json.dumps(evidence)


@pytest.mark.parametrize("shell", ["/bin/bash", "/usr/bin/bash"])
def test_saved_proof_accepts_exact_system_bash_wrapper(shell):
    import shlex

    from scripts.hosted_smoke import verify_execution

    proof = saved_execution()
    for item in proof["items"]:
        item["command"] = shlex.join([shell, "-lc", item["command"]])
    result = verify_execution(**proof, require_probe=False)
    assert result["helper_execution_verified"] and result["skill_reads_verified"]


@pytest.mark.parametrize("shell", ["/workspace/bash", "bash", "/bin/sh"])
def test_saved_proof_rejects_unapproved_shell_wrapper(shell):
    import shlex

    from scripts.hosted_smoke import EvidenceInvalid, verify_execution

    proof = saved_execution()
    for item in proof["items"]:
        item["command"] = shlex.join([shell, "-lc", item["command"]])
    with pytest.raises(EvidenceInvalid):
        verify_execution(**proof, require_probe=False)
