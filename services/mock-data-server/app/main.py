import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.common import APIError, install_errors
from app.api.entities import register
from app.api.openapi import install_openapi
from app.api.snapshot import register as register_snapshot
from app.config import Settings
from app.storage.db import connect
from app.storage.migrations import DIRECTORY

SERVICE_NAME = "mock-data-server"


def create_app() -> FastAPI:
    def database_ready() -> None:
        with connect() as conn:
            count = conn.execute("SELECT count(*) n FROM mock.schema_migrations").fetchone()["n"]
            if count != len(list(DIRECTORY.glob("*.sql"))):
                raise APIError(503, "MIGRATIONS_REQUIRED")

    @asynccontextmanager
    async def lifespan(app):
        Settings.from_env()
        await asyncio.to_thread(database_ready)
        yield

    app = FastAPI(title=SERVICE_NAME, lifespan=lifespan)
    install_errors(app)
    register(app)
    register_snapshot(app)

    @app.get("/health/live")
    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready() -> dict[str, str]:
        database_ready()
        return {"status": "ready"}

    @app.get("/api/v1/ping")
    def ping() -> dict[str, str]:
        return {"message": "pong", "service": SERVICE_NAME}

    install_openapi(app)
    return app


app = create_app()
