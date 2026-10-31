import fcntl
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.config.registry import Registry
from app.config.settings import Settings
from app.storage.database import Database
from app.storage.repositories import SQLiteRepository


@asynccontextmanager
async def maintenance(settings: Settings) -> AsyncIterator[SQLiteRepository]:
    database = Database(settings.database_path)
    database.path.parent.mkdir(parents=True, exist_ok=True)
    with database.path.with_suffix(database.path.suffix + ".owner.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Stop application before maintenance") from None
        try:
            await database.initialize()
            yield SQLiteRepository(
                database,
                Registry.load(settings.config_path),
                run_timeout=settings.run_timeout_seconds,
                recovery_timeout=settings.recovery_timeout_seconds,
                max_concurrent=settings.max_concurrent_runs,
            )
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
