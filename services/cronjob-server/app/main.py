import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.common import APIError, install_errors
from app.api.facade import register
from app.api.openapi import install_openapi
from app.api.reads import register as register_reads
from app.api.runs import register as register_runs
from app.api.settings import register as register_settings
from app.config import Settings
from app.jobs.worker import Worker
from app.source.client import SourceClient
from app.storage.db import connect
from app.storage.migrations import DIRECTORY

SERVICE_NAME = "cronjob-server"


def ready_database() -> None:
    with connect() as conn:
        count = conn.execute("SELECT count(*) n FROM sync.schema_migrations").fetchone()["n"]
        if count != len(list(DIRECTORY.glob("*.sql"))):
            raise APIError(503, "MIGRATIONS_REQUIRED")


def create_app(*, source=None, start_worker: bool = True) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        settings = Settings.from_env()
        await asyncio.to_thread(ready_database)
        app.state.source = source or SourceClient(settings.source_url)
        app.state.worker = Worker(app.state.source, interval=settings.interval)
        if start_worker:
            app.state.worker.start()
        yield
        if start_worker:
            await asyncio.to_thread(app.state.worker.close)

    app = FastAPI(title=SERVICE_NAME, lifespan=lifespan)
    install_errors(app)
    register(app)
    register_reads(app)
    register_runs(app)
    register_settings(app)

    @app.get("/health/live")
    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready() -> dict:
        ready_database()
        if start_worker and (
            not hasattr(app.state, "worker") or not app.state.worker.thread.is_alive()
        ):
            raise APIError(503, "WORKER_UNAVAILABLE")
        return {"status": "ready"}

    @app.get("/api/v1/ping")
    def ping() -> dict[str, str]:
        return {"message": "pong", "service": SERVICE_NAME}

    install_openapi(app)
    return app


app = create_app()
