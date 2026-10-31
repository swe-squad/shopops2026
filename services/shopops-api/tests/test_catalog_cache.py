from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import httpx
import pytest

from app.catalog import SourceCatalog
from app.catalog_source import CatalogConfig
from tests.catalog_fixtures import BASE, HEADERS, SHOP, USER, product


def test_unchanged_revision_reuses_history_but_checks_access_for_every_read(client, source):
    initial = product(client).json()
    source.requests.clear()
    assert product(client).json() == initial
    assert product(client, "sku-b").status_code == 200
    gallery = client.get(BASE, params={"shop_key": SHOP}, headers=HEADERS).json()
    assert gallery["source_revision"] == initial["source_revision"]
    assert gallery["fetched_at"] == initial["fetched_at"]
    assert len(source.requests) == 3
    assert all(request.url.path == "/v1/mock/shops" for request in source.requests)
    assert product(client, "missing-sku").status_code == 404


def test_changed_revision_rebuilds_instead_of_returning_cached_evidence(client, source):
    assert product(client).json()["product"]["unit_cost"] == "12.50"
    source.rows["products"][0]["unit_cost"] = "20.00"
    source.revision += 1
    source.requests.clear()
    response = product(client)
    assert response.status_code == 200
    assert response.json()["product"]["unit_cost"] == "20.00"
    assert response.json()["source_revision"] == 8
    assert any(request.url.path.endswith("/products") for request in source.requests)


def test_revoked_access_cannot_return_cached_shop_or_product(client, source):
    assert product(client).status_code == 200
    source.rows["shops"] = []
    source.revision += 1
    source.requests.clear()
    assert product(client).status_code == 404
    assert client.get(BASE, params={"shop_key": SHOP}, headers=HEADERS).status_code == 404
    assert all(request.url.path.endswith("/shops") for request in source.requests)


@pytest.mark.parametrize("failure", ["outage", "denied", "malformed", "network"])
def test_fresh_access_check_errors_cannot_return_cached_success(client, source, failure):
    assert product(client).status_code == 200

    def fail(request, _resource):
        if failure == "network":
            raise httpx.ConnectError("private source", request=request)
        return httpx.Response(
            403 if failure == "denied" else 503 if failure == "outage" else 200,
            json={"private": "source failure"},
        )

    source.hook = fail
    response = product(client)
    assert response.status_code == (404 if failure == "denied" else 503)
    assert set(response.json()) == {"detail"}


def test_failed_rebuild_does_not_fall_back_to_the_old_revision(client, source):
    assert product(client).status_code == 200
    source.revision += 1
    source.hook = lambda _request, resource: httpx.Response(503) if resource == "products" else None
    assert product(client).status_code == 503
    source.hook = None
    assert product(client).json()["source_revision"] == 8


def test_cache_does_not_mix_identical_skus_from_different_shops(client, source):
    other = "shopify:another-shop"
    for resource, rows in list(source.rows.items()):
        for row in deepcopy(rows):
            copied = row | {"shop_key": other}
            if resource == "products":
                copied["name"] = "Other shop product"
            source.rows[resource].append(copied)
    first = product(client).json()
    second = client.get(
        BASE + "/product", params={"shop_key": other, "sku": "sku-a"}, headers=HEADERS
    ).json()
    source.requests.clear()
    assert product(client).json() == first
    assert (
        client.get(
            BASE + "/product", params={"shop_key": other, "sku": "sku-a"}, headers=HEADERS
        ).json()
        == second
    )
    assert first["product"]["name"] == "Product A"
    assert second["product"]["name"] == "Other shop product"
    assert all(request.url.path.endswith("/shops") for request in source.requests)


def test_cache_evicts_least_recently_used_shop_after_eight_entries(client, source):
    assert product(client).status_code == 200
    for index in range(8):
        other = f"shopify:shop-{index}"
        source.rows["shops"].append(source.rows["shops"][0] | {"shop_key": other})
        source.rows["products"].append(source.rows["products"][0] | {"shop_key": other})
        assert client.get(BASE, params={"shop_key": other}, headers=HEADERS).status_code == 200
    assert len(client.app.state.catalog._cache) == 8
    source.requests.clear()
    assert product(client).status_code == 200
    assert any(request.url.path.endswith("/products") for request in source.requests)


def test_concurrent_same_revision_reads_fetch_history_once(client, source):
    with ThreadPoolExecutor(max_workers=6) as pool:
        responses = list(pool.map(lambda _: product(client), range(12)))
    assert all(response.status_code == 200 for response in responses)
    assert len({response.json()["fetched_at"] for response in responses}) == 1
    assert sum(request.url.path.endswith("/products") for request in source.requests) == 1
    assert sum(request.url.path.endswith("/shops") for request in source.requests) == 13


def test_cache_key_contains_backend_source_and_principal(source):
    provider = SourceCatalog(
        CatalogConfig("http://catalog.test", USER), httpx.MockTransport(source)
    )
    provider.catalog(SHOP)
    assert list(provider._cache) == [("http://catalog.test", USER, SHOP)]
    provider.config = CatalogConfig("http://different-source.test", USER)
    source.requests.clear()
    provider.catalog(SHOP)
    assert any(request.url.path.endswith("/products") for request in source.requests)
