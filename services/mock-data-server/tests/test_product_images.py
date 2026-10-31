from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.storage.db import connect
from app.storage.migrations import migrate
from app.storage.seed import seed
from app.storage.snapshot import snapshot
from tests.test_catalog import PRODUCT, headers, prepare

IMAGE = "https://images.example.com/product.jpg"


def test_migration_upgrade_and_down_preserve_existing_products(database, monkeypatch, tmp_path):
    from app.storage import migrations

    directory = migrations.DIRECTORY
    for path in directory.glob("*.sql"):
        if path.name != "011_product_images.sql":
            (tmp_path / path.name).write_bytes(path.read_bytes())
    with monkeypatch.context() as patch:
        patch.setattr(migrations, "DIRECTORY", tmp_path)
        migrate()
    with connect() as conn:
        conn.execute("INSERT INTO mock.merchants (merchant_id,name) VALUES ('legacy','Legacy')")
        conn.execute(
            "INSERT INTO mock.shops "
            "(shop_key,merchant_id,platform,source_shop_id,name,currency,timezone,capabilities) "
            "VALUES ('shopify:legacy','legacy','shopify','legacy','Legacy','VND','UTC','{}')"
        )
        conn.execute(
            "INSERT INTO mock.products (shop_key,sku,name,unit_cost,cost_basis) "
            "VALUES ('shopify:legacy','CUSTOM','Edited product',123,'custom')"
        )
    migrate()
    migrate()
    with connect() as conn:
        row = conn.execute("SELECT * FROM mock.products").fetchone()
        assert row["name"] == "Edited product"
        assert row["image_url"] is None
        conn.execute((Path("app/rollbacks/011_product_images.sql")).read_text(encoding="utf-8"))
        assert conn.execute("SELECT name FROM mock.products").fetchone()["name"] == row["name"]
    migrate()
    with connect() as conn:
        assert conn.execute("SELECT image_url FROM mock.products").fetchone()["image_url"] is None


def test_product_image_crud_and_validation(database):
    migrate()
    with TestClient(create_app()) as client:
        prepare(client)
        path = "/v1/entities/products"
        response = client.post(path, json=PRODUCT | {"image_url": IMAGE}, headers=headers())
        assert response.status_code == 201, response.text
        assert response.json()["data"]["image_url"] == IMAGE
        key = {k: PRODUCT[k] for k in ("shop_key", "sku")}
        for invalid in ("", "not-a-url", "javascript:alert(1)", "http://example.com/a.jpg"):
            response = client.patch(
                path + "/record", params=key, json={"image_url": invalid}, headers=headers()
            )
            assert response.status_code == 422
        response = client.patch(
            path + "/record", params=key, json={"image_url": None}, headers=headers()
        )
        assert response.json()["data"]["image_url"] is None


def test_seed_includes_images_and_backfill_preserves_edits(database):
    from app.storage.product_images import backfill

    migrate()
    seed()
    with connect() as conn:
        assert (
            conn.execute(
                "SELECT count(*) n FROM mock.products WHERE image_url IS NOT NULL"
            ).fetchone()["n"]
            == 63
        )
        # Simulate an existing database with missing images and operator edits.
        conn.execute("UPDATE mock.products SET image_url=NULL")
        conn.execute(
            "UPDATE mock.products SET image_url=%s WHERE shop_key='shopify:1001' AND sku='CAP'",
            (IMAGE,),
        )
        conn.execute(
            "UPDATE mock.products SET name='Custom product' "
            "WHERE shop_key='shopify:1001' AND sku='TOTE'"
        )
        conn.execute(
            "UPDATE mock.products SET deleted_at=now() "
            "WHERE shop_key='shopify:1001' AND sku='SHIRT-M'"
        )
    before = snapshot()
    assert backfill(apply=False) == {
        "matched": 60,
        "updated": 0,
        "source_revision": before["source_revision"],
    }
    assert snapshot() == before
    result = backfill(apply=True)
    assert result == {
        "matched": 60,
        "updated": 60,
        "source_revision": before["source_revision"] + 1,
    }
    after = snapshot()
    products = [
        p
        for d in after["documents"]
        if d["resource"] == "supplement"
        for p in d["payload"]["products"]
    ]
    assert sum(p["image_url"] is not None for p in products) == 61
    with connect() as conn:
        edited = conn.execute(
            "SELECT image_url FROM mock.products WHERE shop_key='shopify:1001' AND sku='CAP'"
        ).fetchone()
        assert edited["image_url"] == IMAGE
    assert backfill(apply=True)["updated"] == 0
    assert snapshot() == after


def test_backfill_failure_rolls_back_products_and_revision(database, monkeypatch):
    from app.storage import product_images

    migrate()
    seed()
    with connect() as conn:
        conn.execute("UPDATE mock.products SET image_url=NULL")
    before = snapshot()

    def fail(*args):
        raise RuntimeError("snapshot failure")

    monkeypatch.setattr(product_images, "refresh", fail)
    with pytest.raises(RuntimeError, match="snapshot failure"):
        product_images.backfill(apply=True)
    assert snapshot() == before
    with connect() as conn:
        assert (
            conn.execute(
                "SELECT count(*) n FROM mock.products WHERE image_url IS NOT NULL"
            ).fetchone()["n"]
            == 0
        )
