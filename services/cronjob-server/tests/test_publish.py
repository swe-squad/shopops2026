import copy

import pytest

from app.api.common import APIError
from app.pipeline.publish import publish
from app.storage.db import connect
from app.storage.migrations import migrate
from tests.test_normalization import full_snapshot


def test_full_regression_and_replay(database):
    migrate()
    value = full_snapshot()
    result = publish(value)
    assert result["applied_source_revision"] == 1
    assert publish(value)["unchanged"] is True
    with connect() as conn:
        assert conn.execute("SELECT count(*) n FROM core.orders").fetchone()["n"] == 1344
        assert conn.execute("SELECT count(*) n FROM mart.issue_candidates").fetchone()["n"] == 29
        assert (
            conn.execute(
                "SELECT count(*) n FROM mart.issue_candidates "
                "WHERE shop_key='shopee-open-platform:1002'"
            ).fetchone()["n"]
            == 0
        )
        assert conn.execute("SELECT count(*) n FROM raw.documents").fetchone()["n"] == 9


@pytest.mark.parametrize("failure", ["immutable", "missing", "stale"])
def test_failed_publication_preserves_previous_state(database, failure):
    migrate()
    value = full_snapshot()
    publish(value)
    bad = copy.deepcopy(value)
    bad["source_revision"] = 2
    if failure == "immutable":
        supplement = next(d for d in bad["documents"] if d["resource"] == "supplement")
        supplement["payload"]["shop"]["name"] = "changed without version"
    elif failure == "missing":
        removed = bad["documents"][0]
        bad["documents"] = [
            d
            for d in bad["documents"]
            if (d["platform"], d["shop_id"]) != (removed["platform"], removed["shop_id"])
        ]
    else:
        bad["source_revision"] = 0
    with pytest.raises(APIError):
        publish(bad)
    with connect() as conn:
        assert conn.execute("SELECT revision FROM sync.state").fetchone()["revision"] == 1
        assert conn.execute("SELECT count(*) n FROM core.orders").fetchone()["n"] == 1344
