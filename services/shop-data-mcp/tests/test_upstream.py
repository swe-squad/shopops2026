import asyncio
import json
from collections.abc import AsyncIterator

import httpx
import pytest

import app.upstream as upstream_module
from app.upstream import MAX_RESPONSE_BYTES, IntegrationError, Upstream


def test_forwards_exact_refresh_and_service_credential() -> None:
    calls = []
    body = {
        "shop_key": "shop-a",
        "subject": "agent-a",
        "idempotency_key": "refresh-a",
        "dataset_ids": ["orders"],
    }

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.method == "POST"
        assert str(request.url) == "http://srv-captain--collector-dev:8000/v1/refreshes"
        assert request.headers["authorization"] == "Bearer service-credential"
        assert json.loads(request.content) == body
        return httpx.Response(202, json={"operation_id": "op-a", "status": "queued"})

    upstream = Upstream(
        "http://srv-captain--collector-dev:8000",
        "service-credential",
        transport=httpx.MockTransport(handle),
    )
    result = asyncio.run(upstream.request("POST", "/v1/refreshes", body))
    assert result == {"operation_id": "op-a", "status": "queued"}
    assert len(calls) == 1


def test_forwards_grant_subject_and_shop_as_encoded_params() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/grants/grant-a"
        assert dict(request.url.params) == {"subject": "owner+agent", "shop_key": "shop/a"}
        return httpx.Response(200, json={"active": False})

    upstream = Upstream(
        "https://approval.internal", "service", transport=httpx.MockTransport(handle)
    )
    assert asyncio.run(
        upstream.request(
            "GET", "/v1/grants/grant-a", params={"subject": "owner+agent", "shop_key": "shop/a"}
        )
    ) == {"active": False}


@pytest.mark.parametrize("url,token", [(None, None), ("https://internal", None), (None, "x")])
def test_missing_configuration_fails_closed(url: str | None, token: str | None) -> None:
    with pytest.raises(IntegrationError, match="not configured"):
        asyncio.run(Upstream(url, token).request("POST", "/v1/refreshes", {}))


@pytest.mark.parametrize(
    "url",
    ["file:///secret", "https://user:secret@internal", "https://internal?token=secret", "invalid"],
)
def test_invalid_configuration_is_sanitized(url: str) -> None:
    with pytest.raises(IntegrationError, match="configuration is invalid"):
        asyncio.run(Upstream(url, "service").request("POST", "/v1/refreshes", {}))


@pytest.mark.parametrize("status", [301, 302, 400, 401, 403, 404, 429, 500, 503])
def test_unsuccessful_status_does_not_follow_or_disclose_response(status: int) -> None:
    calls = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(status, text="secret payload", headers={"location": "https://evil"})

    upstream = Upstream("https://internal", "service", transport=httpx.MockTransport(handle))
    with pytest.raises(IntegrationError) as failure:
        asyncio.run(upstream.request("POST", "/v1/refreshes", {}))
    assert str(failure.value) == "Integration request failed"
    assert len(calls) == 1


@pytest.mark.parametrize(
    "error", [httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError]
)
def test_transport_failures_are_sanitized_without_retry(error: type[httpx.HTTPError]) -> None:
    calls = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        raise error("secret upstream address and credential", request=request)

    upstream = Upstream("https://internal", "service", transport=httpx.MockTransport(handle))
    with pytest.raises(IntegrationError, match="^Integration is unavailable$"):
        asyncio.run(upstream.request("POST", "/v1/refreshes", {}))
    assert len(calls) == 1


@pytest.mark.parametrize("content", [b"private non-json payload", b"[]", b"null", b'"secret"'])
def test_invalid_json_object_is_sanitized(content: bytes) -> None:
    upstream = Upstream(
        "https://internal",
        "service",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=content)),
    )
    with pytest.raises(IntegrationError, match="^Integration response is invalid$"):
        asyncio.run(upstream.request("GET", "/v1/operations/op-a"))


def test_stream_limit_stops_reading_and_closes_response() -> None:
    class Stream(httpx.AsyncByteStream):
        closed = False

        async def __aiter__(self) -> AsyncIterator[bytes]:
            yield b"x" * MAX_RESPONSE_BYTES
            yield b"x"
            pytest.fail("adapter read beyond the response limit")

        async def aclose(self) -> None:
            self.closed = True

    stream = Stream()
    upstream = Upstream(
        "https://internal",
        "service",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=stream)),
    )
    with pytest.raises(IntegrationError, match="^Integration response exceeds limit$"):
        asyncio.run(upstream.request("GET", "/v1/operations/op-a"))
    assert stream.closed


@pytest.mark.parametrize(
    "path",
    [
        "https://evil/v1/refreshes",
        "//evil/v1/refreshes",
        "/v1/operations/../secret",
        "/v1/grants/a?x=y",
    ],
)
def test_caller_cannot_change_destination(path: str) -> None:
    with pytest.raises(IntegrationError, match="^Integration request is invalid$"):
        asyncio.run(Upstream("https://internal", "service").request("GET", path))


def test_rejects_compressed_response_before_decoding() -> None:
    upstream = Upstream(
        "https://internal",
        "service",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=b"", headers={"Content-Encoding": "gzip"})
        ),
    )
    with pytest.raises(IntegrationError, match="^Integration response is invalid$"):
        asyncio.run(upstream.request("GET", "/v1/operations/op-a"))


def test_total_deadline_stops_slow_responses(monkeypatch: pytest.MonkeyPatch) -> None:
    async def handle(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(1)
        return httpx.Response(200, json={"status": "queued"})

    monkeypatch.setattr(upstream_module, "REQUEST_TIMEOUT_SECONDS", 0.01)
    upstream = Upstream("https://internal", "service", transport=httpx.MockTransport(handle))
    with pytest.raises(IntegrationError, match="^Integration is unavailable$"):
        asyncio.run(upstream.request("GET", "/v1/operations/op-a"))
