import httpx
import pytest

from app.api.common import APIError
from app.source.client import SourceClient


def test_current_access_phone_is_encoded():
    def handler(request):
        assert request.url.params["user_id"] == "+84900000001"
        return httpx.Response(
            200,
            json={
                "user_id": "+84900000001",
                "merchant_ids": ["m1"],
                "shop_keys": ["lazada:1001"],
            },
        )

    client = SourceClient("http://source", transport=httpx.MockTransport(handler))
    assert client.access("+84900000001")["merchant_ids"] == ["m1"]


def test_source_unavailable_and_malformed_success_are_distinct():
    for response, expected in [
        (httpx.Response(503), "SOURCE_UNAVAILABLE"),
        (httpx.Response(200, json=[]), "INVALID_SOURCE_RESPONSE"),
    ]:
        client = SourceClient(
            "http://source", transport=httpx.MockTransport(lambda _, r=response: r)
        )
        with pytest.raises(APIError) as exc:
            client.access("+84900000001")
        assert exc.value.code == expected


def test_response_for_another_user_is_rejected():
    client = SourceClient(
        "http://source",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200, json={"user_id": "+84900000002", "merchant_ids": [], "shop_keys": []}
            )
        ),
    )
    with pytest.raises(APIError, match="Invalid source response"):
        client.access("+84900000001")
