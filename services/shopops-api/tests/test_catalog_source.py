import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.catalog_fixtures import BASE, HEADERS, SHOP, product


def test_pagination_fetches_all_products_and_evidence_pages(client, source):
    template = source.rows["products"][0]
    source.rows["products"] += [template | {"sku": f"sku-{n}"} for n in range(401)]
    template = source.rows["reviews"][0]
    source.rows["reviews"] += [template | {"review_id": f"review-{n}"} for n in range(401)]
    response = client.get(BASE, params={"shop_key": SHOP}, headers=HEADERS)
    assert response.status_code == 200
    assert len(response.json()["products"]) == 403
    assert response.json()["products"][0]["review_count"] == 402
    requests = [r for r in source.requests if r.url.path.endswith("/products")]
    assert [int(r.url.params["offset"]) for r in requests] == [0, 200, 400]
    assert len(product(client).json()["reviews"]) == 402


def test_revision_change_retries_whole_response_and_exposes_only_coherent_result(client, source):
    def change_once(_request, resource):
        if resource == "inventory":
            source.revision = 8
        return None

    source.hook = change_once
    response = product(client)
    assert response.status_code == 200
    assert response.json()["source_revision"] == 8
    assert sum(r.url.path.endswith("/products") for r in source.requests) == 2


def test_continuous_revision_changes_return_sanitized_503_with_bounded_retry(client, source):
    def change_always(_request, _resource):
        source.revision += 1
        return None

    source.hook = change_always
    response = product(client)
    assert response.status_code == 503
    assert response.json() == {"detail": "Catalog source is unavailable"}
    assert len(source.requests) == 6


def test_revision_change_between_pages_restarts_before_returning_a_shop_list(client, source):
    template = source.rows["shops"][0]
    source.rows["shops"] += [template | {"shop_key": f"shopify:{n}"} for n in range(201)]

    def change_once(request, _resource):
        if request.url.params["offset"] == "200":
            source.revision = 8
        return None

    source.hook = change_once
    response = client.get(BASE + "/shops", headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["source_revision"] == 8
    assert len(response.json()["shops"]) == 202


@pytest.mark.parametrize("status", [301, 400, 401, 422, 429, 500, 503])
def test_upstream_errors_do_not_leak_response_or_internal_identity(client, source, status):
    source.hook = lambda _request, _resource: httpx.Response(
        status, json={"error": "+84900000001 source-secret http://private/db"}
    )
    response = product(client)
    assert response.status_code == 503
    assert response.json() == {"detail": "Catalog source is unavailable"}


@pytest.mark.parametrize("status", [403, 404])
def test_upstream_access_denial_hides_selection(client, source, status):
    source.hook = lambda _request, _resource: httpx.Response(status, json={"error": "private"})
    assert product(client).status_code == 404


def test_network_error_is_sanitized(client, source):
    def fail(request, _resource):
        raise httpx.ConnectError("private endpoint/token", request=request)

    source.hook = fail
    assert product(client).json() == {"detail": "Catalog source is unavailable"}


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"data": [], "source_revision": 1},
        {
            "data": [],
            "source_revision": True,
            "pagination": {"limit": 200, "offset": 0, "total": 0},
        },
        {"data": [], "source_revision": -1, "pagination": {"limit": 200, "offset": 0, "total": 0}},
        {"data": [], "source_revision": 7, "pagination": {"limit": 200, "offset": 0, "total": 1}},
        {"data": [], "source_revision": 7, "pagination": {"limit": 200, "offset": 1, "total": 0}},
        {"data": [], "source_revision": 7, "pagination": {"limit": 50, "offset": 0, "total": 0}},
    ],
)
def test_malformed_source_pages_fail_closed(client, source, payload):
    source.hook = lambda _request, _resource: httpx.Response(200, json=payload)
    assert product(client).status_code == 503


def test_invalid_json_is_sanitized(client, source):
    source.hook = lambda _request, _resource: httpx.Response(200, text="private source error")
    assert product(client).status_code == 503


@pytest.mark.parametrize("mutation", ["wrong-shop", "duplicate", "invalid-money", "orphan"])
def test_invalid_source_records_never_become_partial_catalogs(client, source, mutation):
    if mutation == "wrong-shop":

        def wrong_scope(_request, resource):
            if resource == "inventory":
                rows = [source.rows[resource][0] | {"shop_key": "shopify:hidden"}]
                return httpx.Response(
                    200,
                    json={
                        "data": rows,
                        "source_revision": 7,
                        "pagination": {"limit": 200, "offset": 0, "total": 1},
                    },
                )

        source.hook = wrong_scope
    elif mutation == "duplicate":
        source.rows["products"].append(source.rows["products"][0])
    elif mutation == "invalid-money":
        source.rows["products"][0]["unit_cost"] = "NaN"
    else:
        source.rows["order-items"][0]["order_id"] = "missing-order"
    assert product(client).status_code == 503


def test_revoked_current_access_is_rechecked_before_responding(client, source):
    def revoke(_request, resource):
        if resource == "returns":
            source.rows["shops"] = []
            source.revision += 1
        return None

    source.hook = revoke
    response = product(client)
    assert response.status_code == 404
    assert "products" not in response.json()


@pytest.mark.parametrize(
    "environment,expected",
    [
        ({"SHOP_CATALOG_MODE": "typo"}, "SHOP_CATALOG_MODE"),
        ({"SHOP_CATALOG_MODE": "source"}, "CRONJOB_SERVER_URL"),
        ({"CRONJOB_SERVER_URL": "http://user:password@private"}, "CRONJOB_SERVER_URL"),
        ({"CRONJOB_SERVER_URL": "http://localhost:bad"}, "CRONJOB_SERVER_URL"),
        ({"CRONJOB_SERVER_URL": "http://localhost/path"}, "CRONJOB_SERVER_URL"),
        ({"CRONJOB_SERVER_URL": "file:///tmp/source"}, "CRONJOB_SERVER_URL"),
        ({"SHOP_DATA_USER_ID": ""}, "SHOP_DATA_USER_ID"),
        ({"SHOP_DATA_USER_ID": "unverified"}, "SHOP_DATA_USER_ID"),
    ],
)
def test_source_configuration_fails_startup_without_echoing_values(
    tmp_path, monkeypatch, environment, expected
):
    monkeypatch.setenv("SHOP_CATALOG_MODE", "source")
    monkeypatch.setenv("CRONJOB_SERVER_URL", "http://catalog.test")
    monkeypatch.setenv("SHOP_DATA_USER_ID", "+84900000001")
    if environment == {"SHOP_CATALOG_MODE": "source"}:
        monkeypatch.delenv("CRONJOB_SERVER_URL")
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    with pytest.raises(RuntimeError, match=expected) as error:
        with TestClient(create_app(str(tmp_path / "ops.db"), "test-token")):
            pass
    assert "password" not in str(error.value)
