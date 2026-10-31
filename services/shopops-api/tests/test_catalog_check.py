import json

import httpx
import pytest

from app.catalog import SourceCatalog
from app.catalog_check import main
from app.catalog_source import CatalogConfig
from tests.catalog_fixtures import USER


@pytest.fixture(autouse=True)
def catalog_environment(monkeypatch):
    monkeypatch.setenv("SHOP_CATALOG_MODE", "source")
    monkeypatch.setenv("CRONJOB_SERVER_URL", "http://catalog.test")
    monkeypatch.setenv("SHOP_DATA_USER_ID", USER)


def output(capsys):
    captured = capsys.readouterr()
    assert captured.err == ""
    result = json.loads(captured.out)
    assert set(result) == {"status", "shops", "products", "source_revision"}
    return result


def test_preflight_reads_actual_adapter_and_prints_only_coherent_aggregates(source, capsys):
    assert main([], transport=httpx.MockTransport(source)) == 0
    assert output(capsys) == {"status": "ready", "shops": 1, "products": 2, "source_revision": 7}
    assert {request.url.path.removeprefix("/v1/mock/") for request in source.requests} == {
        "shops",
        "products",
        "inventory",
        "orders",
        "order-items",
        "reviews",
        "returns",
    }


def test_preflight_can_inject_provider_without_reading_environment(source, monkeypatch, capsys):
    monkeypatch.setenv("SHOP_CATALOG_MODE", "disabled")
    provider = SourceCatalog(
        CatalogConfig("http://catalog.test", USER), httpx.MockTransport(source)
    )
    assert main([], provider=provider) == 0
    assert output(capsys)["products"] == 2


def test_preflight_counts_every_authorized_shop(source, capsys):
    other = "shopify:other"
    source.rows["shops"].append(source.rows["shops"][0] | {"shop_key": other})
    source.rows["products"].append(source.rows["products"][0] | {"shop_key": other})
    assert main([], transport=httpx.MockTransport(source)) == 0
    assert output(capsys) == {"status": "ready", "shops": 2, "products": 3, "source_revision": 7}


@pytest.mark.parametrize(
    "key,value,status",
    [
        ("SHOP_CATALOG_MODE", "disabled", "disabled"),
        ("SHOP_CATALOG_MODE", "invalid", "invalid_configuration"),
        ("CRONJOB_SERVER_URL", None, "invalid_configuration"),
        ("SHOP_DATA_USER_ID", None, "invalid_configuration"),
        ("CRONJOB_SERVER_URL", "http://private:secret@example.test", "invalid_configuration"),
    ],
)
def test_preflight_configuration_errors_are_sanitized(
    source, monkeypatch, capsys, key, value, status
):
    if value is None:
        monkeypatch.delenv(key)
    else:
        monkeypatch.setenv(key, value)
    assert main([], transport=httpx.MockTransport(source)) == 2
    assert output(capsys) == {"status": status, "shops": 0, "products": 0, "source_revision": None}
    assert source.requests == []


@pytest.mark.parametrize("status", [403, 503])
def test_preflight_source_failure_never_exposes_raw_error(source, capsys, status):
    source.hook = lambda _request, _resource: httpx.Response(
        status, json={"error": "private user shop URL secret"}
    )
    assert main([], transport=httpx.MockTransport(source)) == 2
    assert output(capsys) == {
        "status": "unavailable",
        "shops": 0,
        "products": 0,
        "source_revision": None,
    }


@pytest.mark.parametrize("empty_shops", [False, True])
def test_empty_source_fails_demo_readiness_and_can_be_explicitly_allowed(
    source, capsys, empty_shops
):
    for resource in source.rows:
        if empty_shops or resource != "shops":
            source.rows[resource] = []
    assert main([], transport=httpx.MockTransport(source)) == 1
    expected = {
        "status": "empty",
        "shops": 0 if empty_shops else 1,
        "products": 0,
        "source_revision": 7,
    }
    assert output(capsys) == expected
    assert main(["--allow-empty"], transport=httpx.MockTransport(source)) == 0
    assert output(capsys) == expected


def test_preflight_rejects_revision_change_between_shops_and_catalog(source, capsys):
    def change(_request, resource):
        if resource == "products":
            source.revision = 8

    source.hook = change
    assert main([], transport=httpx.MockTransport(source)) == 2
    assert output(capsys) == {
        "status": "revision_changed",
        "shops": 0,
        "products": 0,
        "source_revision": None,
    }
