import copy
import json
from pathlib import Path

import pytest

from app.api.common import APIError
from app.pipeline.normalize import normalize


def full_snapshot():
    return json.loads(
        (Path(__file__).parent / "fixtures/full_snapshot.json").read_text(encoding="utf-8")
    )


def test_three_platform_normalization():
    normalized = normalize(full_snapshot())
    assert len(normalized["core"]["orders"]) == 1344
    assert len(normalized["core"]["shops"]) == 4
    shopify = [r for r in normalized["core"]["orders"] if r["shop_key"].startswith("shopify:")]
    assert all(r["order_id"].startswith("gid://shopify/Order/") for r in shopify)
    assert all(r["status"] != "completed" for r in shopify)
    lazada = [r for r in normalized["core"]["order_items"] if r["shop_key"].startswith("lazada:")]
    assert all(r["quantity"] == 1 for r in lazada)
    assert normalized["core"]["products"][0]["unit_cost"] is not None


@pytest.mark.parametrize("kind", ["incomplete", "count", "ownership", "missing", "duplicate"])
def test_bad_snapshot_rejected_before_database(kind):
    value = copy.deepcopy(full_snapshot())
    if kind == "incomplete":
        value["complete"] = False
    elif kind == "count":
        value["counts"]["orders"] += 1
    elif kind == "ownership":
        value["documents"][0]["merchant_id"] = "unknown"
    elif kind == "missing":
        value["documents"].pop()
    else:
        value["documents"].append(value["documents"][0])
    with pytest.raises(APIError) as exc:
        normalize(value)
    assert exc.value.code == "INVALID_SNAPSHOT"
