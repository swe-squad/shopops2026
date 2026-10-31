import asyncio
import fcntl
from collections.abc import AsyncIterator, Callable
from contextlib import AsyncExitStack, asynccontextmanager, suppress

from fastapi import APIRouter, FastAPI
from fastapi.responses import JSONResponse
from starlette.routing import Route
from starlette.types import ASGIApp

from app.composition import (
    MCPExactEndpoint,
    build_configured_provider,
    build_configured_router,
    build_mcp_components,
)
from app.config.registry import Registry
from app.config.settings import Settings
from app.contracts.provider import AgentProvider
from app.contracts.tools import ToolBridge
from app.runs.worker import RunWorker
from app.storage.database import Database
from app.storage.repositories import SQLiteRepository, utcnow


def create_app(
    *,
    settings: Settings | None = None,
    provider: AgentProvider | None = None,
    bridge: ToolBridge | None = None,
    api_router: APIRouter | None = None,
    mcp_apps: dict[str, ASGIApp] | None = None,
    router_factory: Callable | None = None,
    mcp_factory: Callable | None = None,
) -> FastAPI:
    """Compose T02/T03/T04 without importing their concrete implementations.

    router_factory(repository, settings, readiness) -> APIRouter.
    mcp_factory(repository, settings) -> dict[mount_path, ASGIApp].
    Concrete factories own auth/provider setup; no test fake is shipped by this module.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        config = settings or Settings.from_env()
        registry = Registry.load(config.config_path)
        database = Database(config.database_path)
        # One OS lock covers migrations, provider coordination and shutdown. A second
        # uvicorn worker or overlapping deployment must never access the DB concurrently.
        database.path.parent.mkdir(parents=True, exist_ok=True)
        lock = database.path.with_suffix(database.path.suffix + ".owner.lock").open("a")
        worker_task = None
        resources = AsyncExitStack()
        try:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError("Database already has an owner") from None
            await database.initialize()
            repository = SQLiteRepository(
                database,
                registry,
                run_timeout=config.run_timeout_seconds,
                recovery_timeout=config.recovery_timeout_seconds,
                max_concurrent=config.max_concurrent_runs,
            )
            app.state.settings = config
            app.state.repository = repository
            selected_provider = provider or build_configured_provider(config, repository)
            app.state.provider = selected_provider
            if provider is None and hasattr(selected_provider, "aclose"):
                resources.push_async_callback(selected_provider.aclose)
            mounts = mcp_factory(repository, config) if mcp_factory else (mcp_apps or {})
            selected_bridge = bridge
            if bridge is None and mcp_factory is None and mcp_apps is None:
                selected_bridge, mounts = build_mcp_components(repository, registry, config)
            app.state.bridge = selected_bridge
            worker = (
                RunWorker(
                    repository,
                    selected_provider,
                    selected_bridge,
                    max_concurrent=config.max_concurrent_runs,
                    max_tool_calls=config.max_tool_calls_per_run,
                    mcp_timeout=config.mcp_timeout_seconds,
                )
                if selected_provider and selected_bridge
                else None
            )
            app.state.worker = worker
            if config.data_mcp_mode == "remote" and "/mcp/data" in mounts:
                raise ValueError("DATA_MCP_MODE=remote cannot mount mock Data MCP")
            for path, asgi in mounts.items():
                if path not in {"/mcp/data", "/mcp/knowledge-memory"}:
                    raise ValueError("Invalid MCP mount")
                child_router = getattr(asgi, "router", None)
                if child_router is not None:
                    await resources.enter_async_context(child_router.lifespan_context(asgi))
                app.router.routes.append(
                    Route(path, MCPExactEndpoint(asgi, path), methods=["POST", "GET", "DELETE"])
                )
                app.mount(path, asgi)
            router = (
                router_factory(repository, config, ready)
                if router_factory
                else api_router
                if api_router is not None
                else build_configured_router(repository, config, ready)
            )
            if router is not None:
                app.include_router(router)
            app.state.adapters_ready = bool(
                worker
                and router is not None
                and "/mcp/knowledge-memory" in mounts
                and (config.data_mcp_mode == "remote" or "/mcp/data" in mounts)
            )
            if worker:
                worker_task = asyncio.create_task(worker.serve())
                # Wait for actual recovery/startup; failure propagates rather than reporting ready.
                while worker.heartbeat is None:
                    if worker_task.done():
                        worker_task.result()
                    await asyncio.sleep(0.001)
            yield
        finally:
            app.state.adapters_ready = False
            try:
                if worker_task:
                    await app.state.worker.stop()
                    with suppress(asyncio.CancelledError):
                        await worker_task
            finally:
                try:
                    await resources.aclose()
                finally:
                    fcntl.flock(lock, fcntl.LOCK_UN)
                    lock.close()

    app = FastAPI(title="agent-core", lifespan=lifespan)
    app.state.adapters_ready = False

    async def ready() -> bool:
        worker = getattr(app.state, "worker", None)
        if (
            not app.state.adapters_ready
            or worker is None
            or worker.heartbeat is None
            or worker.failure
        ):
            return False
        if (utcnow() - worker.heartbeat).total_seconds() > 5:
            return False
        try:
            return await app.state.repository.database.probe()
        except Exception:
            return False

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    async def readiness() -> JSONResponse:
        healthy = await ready()
        return JSONResponse(
            {"status": "ready" if healthy else "not_ready"}, status_code=200 if healthy else 503
        )

    return app


app = create_app()
