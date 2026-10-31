import asyncio
import threading

import pytest


def test_cancelled_transaction_drains_before_owner_can_exit(repo):
    async def execute():
        entered, release = threading.Event(), threading.Event()

        def operation(db):
            db.execute("CREATE TABLE cancel_probe(value TEXT)")
            entered.set()
            assert release.wait(2), "test release deadline exceeded"
            db.execute("INSERT INTO cancel_probe VALUES('committed')")

        task = asyncio.create_task(repo.database.transaction(operation))
        assert await asyncio.to_thread(entered.wait, 2)
        task.cancel()
        await asyncio.sleep(0.01)
        returned_before_commit = task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not returned_before_commit
        value = await repo.database.transaction(
            lambda db: db.execute("SELECT value FROM cancel_probe").fetchone()[0]
        )
        assert value == "committed"

    asyncio.run(execute())
