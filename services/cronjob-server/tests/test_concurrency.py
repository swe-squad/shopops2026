import copy
from concurrent.futures import ThreadPoolExecutor

from app.api.common import APIError
from app.pipeline.publish import publish
from app.storage.db import connect
from app.storage.migrations import migrate
from tests.test_normalization import full_snapshot


def test_concurrent_revisions_cannot_overwrite_newer_publication(database):
    migrate()
    first = full_snapshot()
    newer = copy.deepcopy(first)
    newer["source_revision"] = 2

    def apply(value):
        try:
            return publish(value)
        except APIError as exc:
            assert exc.code == "STALE_SOURCE_REVISION"
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(apply, [first, newer]))
    assert any(r and r["applied_source_revision"] == 2 for r in results)
    with connect() as conn:
        assert conn.execute("SELECT revision FROM sync.state").fetchone()["revision"] == 2
        assert conn.execute("SELECT count(*) n FROM raw.documents").fetchone()["n"] == 9
