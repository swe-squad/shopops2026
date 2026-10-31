import asyncio
import sqlite3
from collections.abc import Callable
from contextlib import closing
from pathlib import Path


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    async def initialize(self) -> None:
        def initialize() -> None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with closing(self.connect()) as db:
                try:
                    db.execute("PRAGMA journal_mode=WAL")
                    version = db.execute("PRAGMA user_version").fetchone()[0]
                    if version > 2:
                        raise RuntimeError("Unsupported database schema")
                    if version == 0:
                        schema = Path(__file__).with_name("migrations").joinpath("001.sql")
                        db.executescript(schema.read_text())
                    if version < 2:
                        schema = Path(__file__).with_name("migrations").joinpath("002.sql")
                        db.executescript(schema.read_text())
                finally:
                    db.close()

        await self._offload(initialize)

    async def transaction[T](self, operation: Callable[[sqlite3.Connection], T]) -> T:
        def transact() -> T:
            db = self.connect()
            try:
                db.execute("BEGIN IMMEDIATE")
                result = operation(db)
                db.commit()
                return result
            except BaseException:
                db.rollback()
                raise
            finally:
                db.close()

        return await self._offload(transact)

    @staticmethod
    async def _offload[T](operation: Callable[[], T]) -> T:
        # Cancellation must not release the application ownership lock while a
        # thread still holds a connection/transaction. Drain even repeated cancels.
        task = asyncio.create_task(asyncio.to_thread(operation))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            while not task.done():
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    continue
                except Exception:
                    break
            if not task.cancelled():
                task.exception()  # consume the drained outcome before propagating cancellation
            raise

    async def probe(self) -> bool:
        return await self.transaction(lambda db: db.execute("SELECT 1").fetchone()[0] == 1)
