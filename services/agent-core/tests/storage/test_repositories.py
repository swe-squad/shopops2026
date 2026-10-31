import asyncio

import pytest


def run(coro):
    return asyncio.run(coro)


async def conversation(repo, scope, key="c"):
    o = await repo.provision(scope, "shopops", "returns-v1")
    return (await repo.create_conversation(scope, o.record.id, key)).record


def test_provision_concurrent_unique(repo, scope):
    async def execute():
        return await asyncio.gather(
            *(repo.provision(scope, "shopops", "returns-v1") for _ in range(12))
        )

    results = run(execute())
    assert len({r.record.id for r in results}) == 1
    assert sum(r.created for r in results) == 1


def test_enqueue_replay_before_busy(repo, scope):
    async def execute():
        c = await conversation(repo, scope)
        first = await repo.enqueue_message(scope, c.id, "m", " xin chào ")
        replay = await repo.enqueue_message(scope, c.id, "m", "xin chào")
        assert first.run.id == replay.run.id
        assert first.message.id == replay.message.id
        assert first.created and not replay.created
        from app.contracts.errors import ConversationBusy

        with pytest.raises(ConversationBusy):
            await repo.enqueue_message(scope, c.id, "other", "follow-up")

    run(execute())


def test_same_key_different_payload_conflicts(repo, scope):
    from app.contracts.errors import IdempotencyConflict

    async def execute():
        c = await conversation(repo, scope)
        await repo.enqueue_message(scope, c.id, "m", "first")
        with pytest.raises(IdempotencyConflict):
            await repo.enqueue_message(scope, c.id, "m", "second")
        other = await repo.provision(
            scope.model_copy(update={"shop_id": "shop-b"}), "shopops", "returns-v1"
        )
        with pytest.raises(IdempotencyConflict):
            await repo.create_conversation(scope, other.record.id, "c")

    run(execute())


@pytest.mark.parametrize("field", ["tenant_id", "shop_id", "user_id"])
def test_cross_scope_repository_access_denied(repo, scope, field):
    from app.contracts.errors import NotFound

    async def execute():
        c = await conversation(repo, scope)
        r = await repo.enqueue_message(scope, c.id, "m", "hello")
        foreign = scope.model_copy(update={field: "foreign"})
        for operation in (
            repo.get_run(foreign, r.run.id),
            repo.get_history(foreign, c.id),
            repo.get_events(foreign, r.run.id),
            repo.get_config_snapshot(foreign, c.id),
        ):
            with pytest.raises(NotFound):
                await operation

    run(execute())


def test_stable_cursor_rejects_foreign_resource(repo, scope):
    from app.contracts.errors import InvalidCursor

    async def execute():
        a = await conversation(repo, scope, "a")
        b = await conversation(repo, scope, "b")
        result = await repo.enqueue_message(scope, a.id, "m", "hello")
        page = await repo.get_history(scope, a.id, limit=1)
        assert page.items[0].content == "hello"
        with pytest.raises(InvalidCursor):
            await repo.get_history(scope, b.id, after=result.message.id)

    run(execute())


def test_revision_activation_preserves_snapshot(repo, scope, registry):
    from app.contracts.errors import ConfigurationConflict

    async def execute():
        old = await conversation(repo, scope, "old")
        new = registry.get("shopops", "returns-v1").model_copy(
            update={"revision": "returns-v2", "data_mcp_url": "http://localhost:9999/mcp/data"}
        )
        registry.register(new)
        with pytest.raises(ConfigurationConflict):
            await repo.provision(scope, "shopops", "returns-v2")
        await repo.activate_revision(scope, "shopops", "returns-v2")
        current = await conversation_active(repo, scope)
        assert (await repo.get_config_snapshot(scope, old.id)).revision == "returns-v1"
        assert (await repo.get_config_snapshot(scope, current.id)).revision == "returns-v2"

    async def conversation_active(repo, scope):
        o = await repo.provision(scope, "shopops", "returns-v2")
        return (await repo.create_conversation(scope, o.record.id, "new")).record

    run(execute())


def test_claim_limit_is_atomic_across_conversations(repo, scope):
    async def execute():
        for i in range(6):
            c = await conversation(repo, scope, str(i))
            await repo.enqueue_message(scope, c.id, str(i), "hello")
        claims = await asyncio.gather(*(repo.claim_next_run() for _ in range(8)))
        assert sum(r is not None for r in claims) == 4

    run(execute())


def test_retention_keeps_nonterminal_content_and_monotonic_sequences(repo, scope):
    from datetime import timedelta

    from app.runs.worker import RunWorker
    from tests.runs.doubles import ControlledBridge, ControlledProvider

    async def execute():
        c = await conversation(repo, scope)
        await repo.enqueue_message(scope, c.id, "m", "hello")
        await RunWorker(repo, ControlledProvider(), ControlledBridge()).tick()
        await repo.prune((repo.clock() + timedelta(seconds=1)).isoformat())
        new = await repo.enqueue_message(scope, c.id, "next", "next")
        assert new.message.sequence == 3
        await repo.prune((repo.clock() + timedelta(days=1)).isoformat())
        assert (await repo.get_history(scope, c.id)).items[0].content == "next"

    run(execute())


def test_replay_after_retention_preserves_message_receipt(repo, scope):
    from datetime import timedelta

    from app.runs.worker import RunWorker
    from tests.runs.doubles import ControlledBridge, ControlledProvider

    async def execute():
        c = await conversation(repo, scope)
        original = await repo.enqueue_message(scope, c.id, "m", "hello")
        await RunWorker(repo, ControlledProvider(), ControlledBridge()).tick()
        await repo.prune((repo.clock() + timedelta(seconds=1)).isoformat())
        replay = await repo.enqueue_message(scope, c.id, "m", "hello")
        assert not replay.created
        assert replay.run.id == original.run.id
        assert replay.message.id == original.message.id
        assert replay.message.sequence == original.message.sequence
        assert replay.message.created_at == original.message.created_at
        assert (await repo.get_history(scope, c.id)).items == ()

    run(execute())


def test_worker_uses_durable_message_permission_snapshot(repo, scope):
    from app.storage.repositories import SQLiteRepository

    async def execute():
        privileged = scope.model_copy(
            update={"permissions": frozenset({"conversation:write", "history:read"})}
        )
        limited = scope.model_copy(update={"permissions": frozenset({"conversation:write"})})
        c = await conversation(repo, privileged)
        result = await repo.enqueue_message(limited, c.id, "m", "hello")
        reopened = SQLiteRepository(repo.database, repo.registry)
        context, _ = await reopened.execution_context(result.run.id)
        assert context.scope.permissions == frozenset({"conversation:write"})
        assert "history:read" not in context.scope.permissions

    run(execute())
