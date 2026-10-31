import asyncio

import pytest

from app.contracts.errors import IdempotencyConflict, InvalidInput
from app.contracts.runtime import RuntimeProfile


def hosted(registry):
    original = registry.snapshots()[0]
    profile = RuntimeProfile(
        profile_id="shopops-hosted-v1",
        environment_type="openai_hosted",
        bundle_id="shopops-hosted-v1",
        bundle_version="1",
        bundle_sha256="a" * 64,
        container_size="small",
        multi_agent_enabled=True,
        max_concurrent_subagents=2,
    )
    revision = original.model_copy(update={"revision": "hosted-test", "runtime_profile": profile})
    registry.register(revision)
    return revision


async def create(repo, scope, revision="returns-v1"):
    o = await repo.provision(scope, "shopops", revision)
    return (await repo.create_conversation(scope, o.record.id, "c")).record


def test_output_mode_replay_conflict(repo, scope, registry):
    async def scenario():
        hosted(registry)
        c = await create(repo, scope, "hosted-test")
        first = await repo.enqueue_message(scope, c.id, "m", "hello", output_mode="report")
        replay = await repo.enqueue_message(scope, c.id, "m", "hello", output_mode="report")
        assert replay.run.id == first.run.id
        assert replay.run.output_mode == "report"
        with pytest.raises(IdempotencyConflict):
            await repo.enqueue_message(scope, c.id, "m", "hello")

    asyncio.run(scenario())


def test_legacy_rejects_report(repo, scope):
    async def scenario():
        c = await create(repo, scope)
        with pytest.raises(InvalidInput):
            await repo.enqueue_message(scope, c.id, "m", "hello", output_mode="report")

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("mode", "kind", "state"),
    [
        ("report", "answer", "failed"),
        ("report", "clarification", "completed"),
        ("report", "cannot_answer", "completed"),
        ("text", "answer", "completed"),
    ],
)
def test_root_report_requirements(repo, scope, registry, mode, kind, state):
    from app.contracts.models import ApplicationResponse
    from app.contracts.provider import ProviderSnapshot
    from app.runs.worker import RunWorker

    class Provider:
        async def list_artifacts(self, session_id, turn_id):
            return ()

    async def scenario():
        hosted(registry)
        c = await create(repo, scope, "hosted-test")
        r = (await repo.enqueue_message(scope, c.id, "m", "hello", output_mode=mode)).run
        await repo.claim_next_run()
        await repo.save_session_mapping(r.id, "session")
        await repo.mark_submission(r.id, "submitted", "root")
        snapshot = ProviderSnapshot(
            session_id="session",
            root_turn_id="root",
            input_run_id=r.id,
            root_status="completed",
            item_id="item",
            response=ApplicationResponse(kind=kind, text="OK"),
        )
        worker = RunWorker(repo, Provider(), None)
        await worker._consume(await repo.get_run(scope, r.id), snapshot)
        result = await repo.get_run(scope, r.id)
        assert result.state == state
        if state == "failed":
            assert result.error == "artifact_invalid"

    asyncio.run(scenario())


def test_failed_environment_blocks_without_new_session(repo, scope, registry):
    from app.contracts.provider import ProviderSnapshot
    from app.contracts.runtime import ProviderEnvironment
    from app.runs.worker import RunWorker

    async def scenario():
        hosted(registry)
        c = await create(repo, scope, "hosted-test")
        run = (await repo.enqueue_message(scope, c.id, "m", "hello")).run
        await repo.claim_next_run()
        await repo.save_session_mapping(run.id, "session", input_submitted=True)
        snapshot = ProviderSnapshot(
            session_id="session",
            root_turn_id="root",
            root_status="failed",
            input_run_id=run.id,
            environment=ProviderEnvironment(id="env", state="unavailable"),
        )
        await RunWorker(repo, None, None)._consume(await repo.get_run(scope, run.id), snapshot)
        result = await repo.get_run(scope, run.id)
        assert result.error == "environment_unavailable"
        assert (await repo.get_conversation(scope, c.id)).status == "blocked"
        assert (await repo.get_runtime(scope, c.id)).id == "env"

    asyncio.run(scenario())


def test_report_metrics_and_source_provenance():
    import json

    from app.contracts.errors import ArtifactInvalid
    from app.contracts.models import Source
    from app.contracts.tools import ToolResult
    from app.runs.artifacts import validate_report

    metrics = {
        "start_date": "2026-01-01",
        "end_date": "2026-01-02",
        "orders": 10,
        "returns": 2,
        "return_rate": 20.0,
        "sku": "sku",
        "timezone": "Asia/Ho_Chi_Minh",
        "baseline": {
            "start_date": "2025-12-30",
            "end_date": "2025-12-31",
            "orders": 10,
            "returns": 1,
            "return_rate": 10.0,
        },
        "change_percentage_points": 10.0,
    }
    data = Source(type="data", reference="metrics:one")
    knowledge = Source(type="knowledge", reference="policy:one")
    report = {
        "schema_version": "1",
        "metrics": metrics,
        "knowledge_findings": [{"reference": "policy:one", "finding": "Policy"}],
        "sources": [data.model_dump(), knowledge.model_dump()],
    }
    results = (
        ToolResult(data=metrics, sources=(data,)),
        ToolResult(data={"text": "Policy"}, sources=(knowledge,)),
    )
    validate_report(json.dumps(report).encode(), results)
    for invalid in (
        report | {"extra": "forbidden"},
        report | {"sources": [data.model_dump()]},
        report
        | {
            "metrics": metrics
            | {"orders": 20, "return_rate": 10.0, "change_percentage_points": 0.0}
        },
    ):
        with pytest.raises(ArtifactInvalid):
            validate_report(json.dumps(invalid).encode(), results)


def test_report_requires_matching_metrics_source():
    import json

    from app.contracts.errors import ArtifactInvalid
    from app.contracts.models import Source
    from app.contracts.tools import ToolResult
    from app.runs.artifacts import validate_report

    metrics = {
        "start_date": "a",
        "end_date": "b",
        "orders": 10,
        "returns": 2,
        "return_rate": 20.0,
        "sku": "sku",
        "timezone": "Asia/Ho_Chi_Minh",
        "baseline": {
            "start_date": "c",
            "end_date": "d",
            "orders": 10,
            "returns": 1,
            "return_rate": 10.0,
        },
        "change_percentage_points": 10.0,
    }
    original = Source(type="data", reference="original")
    other = Source(type="data", reference="other")
    knowledge = Source(type="knowledge", reference="policy")
    report = {
        "schema_version": "1",
        "metrics": metrics,
        "knowledge_findings": [{"reference": "policy", "finding": "Policy"}],
        "sources": [other.model_dump(), knowledge.model_dump()],
    }
    with pytest.raises(ArtifactInvalid):
        validate_report(
            json.dumps(report).encode(),
            (ToolResult(data=metrics, sources=(original,)), ToolResult(sources=(other, knowledge))),
        )


def test_hosted_format_directive_reaches_provider(repo, scope, registry):
    from app.contracts.errors import ProviderRequestRejected
    from app.runs.worker import RunWorker

    class Provider:
        received = None

        async def create_session(self, config, correlation_id, *, initial_input=None):
            self.received = initial_input
            raise ProviderRequestRejected()

    async def scenario():
        hosted(registry)
        c = await create(repo, scope, "hosted-test")
        await repo.enqueue_message(scope, c.id, "m", "hello", output_mode="report")
        run = await repo.claim_next_run()
        provider = Provider()
        await RunWorker(repo, provider, None).execute(run)
        assert "report.json" in provider.received
        assert provider.received.startswith("hello")

    asyncio.run(scenario())


def test_output_mode_hash_collision_cannot_replay(repo, scope, registry):
    async def scenario():
        hosted(registry)
        c = await create(repo, scope, "hosted-test")
        await repo.enqueue_message(scope, c.id, "m", "report\0hello")
        with pytest.raises(IdempotencyConflict):
            await repo.enqueue_message(scope, c.id, "m", "hello", output_mode="report")

    asyncio.run(scenario())


def test_artifact_recovery_reuses_validated_metadata(repo, scope, registry):
    from app.contracts.models import ApplicationResponse
    from app.runs.artifacts import finalize_artifacts

    class Files:
        calls = 0

        async def list_artifacts(self, session_id, turn_id):
            self.calls += 1
            if self.calls > 1:
                raise OSError("expired after validation")
            return ()

    async def scenario():
        hosted(registry)
        c = await create(repo, scope, "hosted-test")
        r = (await repo.enqueue_message(scope, c.id, "m", "hello")).run
        await repo.claim_next_run()
        await repo.save_session_mapping(r.id, "session")
        await repo.mark_submission(r.id, "submitted", "root")
        files = Files()
        response = ApplicationResponse(kind="answer", text="OK")
        await finalize_artifacts(repo, files, r, "session", "root", response)
        # Simulate restart after metadata commit but before root completion.
        from app.storage.repositories import SQLiteRepository

        reopened = SQLiteRepository(repo.database, registry)
        await finalize_artifacts(reopened, files, r, "session", "root", response)
        await reopened.complete_run(r.id, "root", "item", response)
        assert (await reopened.get_run(scope, r.id)).state == "completed"
        assert files.calls == 1

    asyncio.run(scenario())


def test_setup_timeout_cancels_root_and_preserves_environment(repo, scope, registry):
    from datetime import timedelta

    from app.contracts.provider import ProviderSnapshot
    from app.contracts.runtime import ProviderEnvironment
    from app.runs.worker import RunWorker

    class Provider:
        cancelled = False

        async def cancel_turn(self, session_id, turn_id):
            self.cancelled = True

        async def inspect_session(self, session_id):
            return ProviderSnapshot(
                session_id=session_id, root_turn_id="root", root_status="cancelled"
            )

    async def scenario():
        hosted(registry)
        c = await create(repo, scope, "hosted-test")
        r = (await repo.enqueue_message(scope, c.id, "m", "hello")).run
        await repo.claim_next_run()
        await repo.save_session_mapping(r.id, "session")
        await repo.mark_submission(r.id, "submitted", "root")
        snapshot = ProviderSnapshot(
            session_id="session",
            root_turn_id="root",
            root_status="running",
            environment=ProviderEnvironment(id="env", state="provisioning"),
        )
        provider = Provider()
        worker = RunWorker(repo, provider, None, clock=lambda: r.created_at + timedelta(seconds=61))
        await worker._consume(await repo.get_run(scope, r.id), snapshot)
        assert provider.cancelled
        assert (await repo.get_run(scope, r.id)).error == "environment_timeout"
        assert (await repo.get_runtime(scope, c.id)).id == "env"

    asyncio.run(scenario())


def test_setup_budget_starts_at_creation_not_enqueue(repo, scope, registry):
    from datetime import timedelta

    from app.contracts.provider import ProviderSnapshot
    from app.contracts.runtime import ProviderEnvironment
    from app.runs.worker import RunWorker

    async def scenario():
        hosted(registry)
        c = await create(repo, scope, "hosted-test")
        r = (await repo.enqueue_message(scope, c.id, "m", "hello")).run
        await repo.claim_next_run()
        repo.clock = lambda: r.created_at + timedelta(seconds=30)
        await repo.mark_submission(r.id, "session_creating")
        await repo.save_session_mapping(r.id, "session", input_submitted=True)
        await repo.mark_submission(r.id, "submitted", "root")
        snapshot = ProviderSnapshot(
            session_id="session",
            root_turn_id="root",
            root_status="running",
            environment=ProviderEnvironment(id="env", state="provisioning"),
        )
        worker = RunWorker(repo, None, None, clock=lambda: r.created_at + timedelta(seconds=61))
        assert not await worker._consume(await repo.get_run(scope, r.id), snapshot)
        current = await repo.get_run(scope, r.id)
        assert current.runtime_setup_started_at == r.created_at + timedelta(seconds=30)

    asyncio.run(scenario())
