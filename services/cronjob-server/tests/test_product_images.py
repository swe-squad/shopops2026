from pathlib import Path

import pytest

from app.api.common import APIError
from app.pipeline.normalize import normalize
from app.pipeline.publish import publish
from app.storage.db import connect
from app.storage.migrations import migrate
from tests.test_normalization import full_snapshot

IMAGE = "https://images.example.com/product.jpg"


def test_image_survives_publication_and_legacy_snapshots(database):
    migrate()
    legacy = full_snapshot()
    assert all(p["image_url"] is None for p in normalize(legacy)["core"]["products"])
    publish(legacy)
    value = full_snapshot()
    value["source_revision"] = 2
    for doc in value["documents"]:
        if doc["resource"] == "supplement":
            doc["document_id"] += "/images"
            doc["resource_revision"] = 2
            for product in doc["payload"]["products"]:
                product["image_url"] = IMAGE
    publish(value)
    assert publish(value)["unchanged"] is True
    with connect() as conn:
        assert (
            conn.execute(
                "SELECT count(*) n FROM core.products WHERE image_url=%s", (IMAGE,)
            ).fetchone()["n"]
            == 12
        )
        assert conn.execute("SELECT count(*) n FROM raw.documents").fetchone()["n"] == 13


def test_image_migration_down_and_reapply_preserve_products(database):
    migrate()
    publish(full_snapshot())
    with connect() as conn:
        conn.execute(Path("app/rollbacks/007_product_images.sql").read_text(encoding="utf-8"))
        assert conn.execute("SELECT count(*) n FROM core.products").fetchone()["n"] == 12
    migrate()
    migrate()
    with connect() as conn:
        assert (
            conn.execute("SELECT count(*) n FROM core.products WHERE image_url IS NULL").fetchone()[
                "n"
            ]
            == 12
        )


def test_invalid_image_snapshot_is_rejected():
    value = full_snapshot()
    doc = next(d for d in value["documents"] if d["resource"] == "supplement")
    doc["payload"]["products"][0]["image_url"] = "javascript:alert(1)"
    with pytest.raises(APIError):
        normalize(value)
