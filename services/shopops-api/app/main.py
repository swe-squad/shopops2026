import os
import secrets
import sqlite3
from collections.abc import Iterator
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException

from app import navigation, operations


def create_app(database: str | None = None, token: str | None = None) -> FastAPI:
    db_path = database or os.environ.get("SHOP_DATA_PATH", "/data/shopops.sqlite3")
    access_token = token or os.environ.get("SHOP_API_TOKEN", "")

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if not access_token:
            raise RuntimeError("SHOP_API_TOKEN is required")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db_path) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS incidents (id INTEGER PRIMARY KEY, "
                "title TEXT NOT NULL, detail TEXT NOT NULL, "
                "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS navigation (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "url TEXT NOT NULL)"
            )
        yield

    app = FastAPI(title="ShopOps API", lifespan=lifespan)

    def authorize(authorization: Annotated[str | None, Header()] = None) -> None:
        expected = f"Bearer {access_token}"
        if (
            not access_token
            or not authorization
            or not secrets.compare_digest(authorization.encode(), expected.encode())
        ):
            raise HTTPException(status_code=401, detail="Unauthorized")

    @contextmanager
    def connect() -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(db_path)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(operations.router(connect, authorize))
    app.include_router(navigation.router(connect, authorize))

    return app


app = create_app()
