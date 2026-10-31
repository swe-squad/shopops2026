import asyncio
import sqlite3
from pathlib import Path

from app.storage.database import Database


def test_upgrade_existing_database_and_reopen(tmp_path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as db:
        db.executescript(Path("app/storage/migrations/001.sql").read_text())
    database = Database(path)
    asyncio.run(database.initialize())
    asyncio.run(database.initialize())
    with database.connect() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 2
        assert db.execute("SELECT name FROM sqlite_master WHERE name='artifacts'").fetchone()
        assert db.execute("SELECT name FROM sqlite_master WHERE name='runtime_mappings'").fetchone()


def test_pinned_runtime_survives_activation_and_reopen(repo, scope, registry):
    from app.contracts.runtime import ProviderEnvironment, RuntimeProfile
    from app.storage.repositories import SQLiteRepository

    async def scenario():
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
        hosted = original.model_copy(update={"revision": "hosted-test", "runtime_profile": profile})
        registry.register(hosted)
        o = await repo.provision(scope, original.template_id, original.revision)
        old = (await repo.create_conversation(scope, o.record.id, "old")).record
        await repo.activate_revision(scope, original.template_id, hosted.revision)
        new = (await repo.create_conversation(scope, o.record.id, "new")).record
        env = ProviderEnvironment(id="env-one", state="connected")
        await repo.save_session_mapping(
            (await repo.enqueue_message(scope, new.id, "m", "hello")).run.id, "session-one"
        )
        await repo.save_runtime(scope, new.id, env)
        reopened = SQLiteRepository(Database(repo.database.path), registry)
        assert (
            await reopened.get_conversation(scope, old.id)
        ).config.runtime_profile.environment_type == "none"
        assert (await reopened.get_conversation(scope, new.id)).config.runtime_profile == profile
        assert await reopened.get_runtime(scope, new.id) == env

    asyncio.run(scenario())
