import asyncio

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from tests.runs.doubles import ControlledBridge, ControlledProvider
from tests.storage.test_repositories import conversation


def environment(tmp_path):
    return {
        "APP_ENV": "test",
        "AGENT_PROVIDER": "fake",
        "AUTH_MODE": "fixture",
        "DATABASE_URL": f"sqlite:///{tmp_path / 'runtime.db'}",
        "CONFIG_PATH": "config/registry.json",
        "DATA_MCP_MODE": "mock",
        "DATA_MCP_URL": "http://127.0.0.1:8000/mcp/data",
        "KNOWLEDGE_MEMORY_MCP_URL": "http://127.0.0.1:8000/mcp/knowledge-memory",
        "MCP_TOKEN_SIGNING_KEY": "synthetic-test-key-not-a-real-credential",
    }


@pytest.mark.parametrize("mode", ["production", "develop"])
def test_fixture_and_fake_are_rejected_outside_local_test(tmp_path, mode):
    from app.config.settings import Settings

    env = environment(tmp_path) | {"APP_ENV": mode}
    with pytest.raises(ValueError, match="AUTH_MODE|AGENT_PROVIDER") as error:
        Settings.from_env(env)
    assert env["MCP_TOKEN_SIGNING_KEY"] not in str(error.value)


@pytest.mark.parametrize("missing", ["DATABASE_URL", "AGENT_PROVIDER", "MCP_TOKEN_SIGNING_KEY"])
def test_missing_configuration_names_only(tmp_path, missing):
    from app.config.settings import Settings

    env = environment(tmp_path)
    del env[missing]
    with pytest.raises(ValueError, match=missing):
        Settings.from_env(env)


def test_live_mode_requires_key_and_explicit_model(tmp_path):
    from app.config.settings import Settings

    env = environment(tmp_path) | {"AGENT_PROVIDER": "openai_agents"}
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        Settings.from_env(env)
    env["OPENAI_API_KEY"] = "synthetic"
    with pytest.raises(ValueError, match="OPENAI_MODEL"):
        Settings.from_env(env)


def test_live_provider_is_composed_without_network_at_startup(tmp_path):
    from app.config.settings import Settings
    from app.main import create_app

    env = environment(tmp_path) | {
        "AGENT_PROVIDER": "openai_agents",
        "OPENAI_API_KEY": "synthetic",
        "OPENAI_MODEL": "synthetic",
    }
    app = create_app(settings=Settings.from_env(env))
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/ready").status_code == 200
        assert app.state.provider.__class__.__name__ == "OpenAIAgentsProvider"


def test_lifespan_composes_shared_repository_and_stops_worker(tmp_path):
    from app.config.settings import Settings
    from app.main import create_app

    seen = []

    def router_factory(repo, settings, readiness):
        seen.append(repo)
        router = APIRouter()

        @router.get("/test-wiring")
        async def status():
            return {"ready": await readiness()}

        return router

    app = create_app(
        settings=Settings.from_env(environment(tmp_path)),
        provider=ControlledProvider(),
        bridge=ControlledBridge(),
        router_factory=router_factory,
        mcp_factory=lambda repo, settings: {
            "/mcp/data": FastAPI(),
            "/mcp/knowledge-memory": FastAPI(),
        },
    )
    with TestClient(app) as client:
        assert seen == [app.state.repository]
        assert client.get("/ready").status_code == 200
        assert client.get("/test-wiring").json() == {"ready": True}
    assert app.state.worker.heartbeat is None


def test_second_database_owner_is_rejected(tmp_path):
    from app.config.settings import Settings
    from app.main import create_app

    settings = Settings.from_env(environment(tmp_path))
    with TestClient(create_app(settings=settings)):
        with pytest.raises(RuntimeError, match="Database already has an owner"):
            with TestClient(create_app(settings=settings)):
                pass


def test_database_restart_preserves_queue_and_mapping(repo, scope):
    from app.runs.worker import RunWorker
    from app.storage.database import Database
    from app.storage.repositories import SQLiteRepository

    async def execute():
        c = await conversation(repo, scope)
        result = await repo.enqueue_message(scope, c.id, "m", "hello")
        await repo.save_session_mapping(result.run.id, "session-a")
        database = Database(repo.database.path)
        await database.initialize()
        reopened = SQLiteRepository(database, repo.registry)
        worker = RunWorker(reopened, ControlledProvider(), ControlledBridge())
        await worker.startup()
        await worker.tick()
        assert (await reopened.get_run(scope, result.run.id)).state == "completed"
        assert (await reopened.get_conversation(scope, c.id)).provider_session_id == "session-a"
        assert len((await reopened.get_history(scope, c.id)).items) == 2

    asyncio.run(execute())


def test_provider_cleanup_failure_remains_visible(repo, scope):
    from app.runs.worker import RunWorker

    async def execute():
        c = await conversation(repo, scope)
        result = await repo.enqueue_message(scope, c.id, "m", "hello")
        provider = ControlledProvider()
        worker = RunWorker(repo, provider, ControlledBridge())
        await worker.tick()
        assert (await repo.get_run(scope, result.run.id)).state == "completed"
        provider.delete_fails = True
        with pytest.raises(TimeoutError):
            await repo.delete_conversation(scope, c.id, provider.delete_session)
        assert (await repo.get_conversation(scope, c.id)).status == "cleanup_failed"
        provider.delete_fails = False
        await repo.delete_conversation(scope, c.id, provider.delete_session)
        from app.contracts.errors import NotFound

        with pytest.raises(NotFound):
            await repo.get_conversation(scope, c.id)

    asyncio.run(execute())


def test_mount_lifespan_is_started_and_closed(tmp_path):
    from contextlib import asynccontextmanager

    from app.config.settings import Settings
    from app.main import create_app

    lifecycle = []

    @asynccontextmanager
    async def lifespan(app):
        lifecycle.append("started")
        yield
        lifecycle.append("stopped")

    app = create_app(
        settings=Settings.from_env(environment(tmp_path)),
        mcp_apps={"/mcp/knowledge-memory": FastAPI(lifespan=lifespan)},
    )
    with TestClient(app):
        assert lifecycle == ["started"]
    assert lifecycle == ["started", "stopped"]
