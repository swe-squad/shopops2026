"""Bounded service-to-service transport for proposed integration contracts."""

import asyncio
import json
import logging
import re
from typing import Any

import httpx

MAX_RESPONSE_BYTES = 1024 * 1024
REQUEST_TIMEOUT_SECONDS = 15
_GET_PATH = re.compile(r"/v1/(?:operations|grants)/[A-Za-z0-9_-]{1,128}")
_POST_PATHS = {"/v1/refreshes", "/v1/raw-access-requests"}


def _omit_request_url(record: logging.LogRecord) -> bool:
    # HTTPX logs complete URLs at INFO; CRUD query keys can contain phone numbers.
    return not str(record.msg).startswith("HTTP Request:")


logging.getLogger("httpx").addFilter(_omit_request_url)


class IntegrationError(ValueError):
    """Safe integration failure that may be returned to an MCP caller."""


class Upstream:
    """Use only operator configuration, never a caller's URL or bearer token."""

    def __init__(
        self,
        base_url: str | None,
        token: str | None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url
        self._token = token
        self._transport = transport

    def _configured_url(self) -> str:
        if not self._base_url or not self._token or not self._token.strip():
            raise IntegrationError("Integration is not configured")
        try:
            url = httpx.URL(self._base_url)
        except httpx.InvalidURL:
            raise IntegrationError("Integration configuration is invalid") from None
        if (
            url.scheme not in {"http", "https"}
            or not url.host
            or url.userinfo
            or url.query
            or url.fragment
            or url.path not in {"", "/"}
            or any(ord(char) < 32 or ord(char) == 127 for char in self._token)
        ):
            raise IntegrationError("Integration configuration is invalid")
        return str(url).rstrip("/")

    def allows(self, method: str, path: str) -> bool:
        return bool(
            (method == "POST" and path in _POST_PATHS)
            or (method == "GET" and _GET_PATH.fullmatch(path))
        )

    async def request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        *,
        phone: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        base_url = self._configured_url()
        if not self.allows(method, path):
            raise IntegrationError("Integration request is invalid")
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
            "Accept-Encoding": "identity",
        }
        if phone is not None:
            if not re.fullmatch(r"\+[1-9][0-9]{7,14}", phone):
                raise IntegrationError("Integration identity is invalid")
            headers["X-Demo-User-Id"] = phone
        if idempotency_key is not None:
            if not re.fullmatch(r"[!-~]{1,200}", idempotency_key):
                raise IntegrationError("Integration idempotency key is invalid")
            headers["Idempotency-Key"] = idempotency_key
        try:
            # An outer deadline also bounds servers that trickle bytes below the read timeout.
            async with asyncio.timeout(REQUEST_TIMEOUT_SECONDS):
                async with httpx.AsyncClient(
                    transport=self._transport,
                    timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS, connect=5),
                    follow_redirects=False,
                    trust_env=False,
                ) as client:
                    async with client.stream(
                        method,
                        base_url + path,
                        json=body,
                        params=params,
                        headers=headers,
                    ) as response:
                        if not 200 <= response.status_code < 300:
                            raise IntegrationError("Integration request failed")
                        # Refuse compression so decompression cannot allocate an unbounded buffer.
                        if response.headers.get("content-encoding", "identity") != "identity":
                            raise IntegrationError("Integration response is invalid")
                        content = bytearray()
                        async for chunk in response.aiter_bytes():
                            if len(content) + len(chunk) > MAX_RESPONSE_BYTES:
                                raise IntegrationError("Integration response exceeds limit")
                            content.extend(chunk)
            result = json.loads(content)
            if not isinstance(result, dict):
                raise IntegrationError("Integration response is invalid")
            return result
        except (httpx.HTTPError, TimeoutError):
            raise IntegrationError("Integration is unavailable") from None
        except (UnicodeError, json.JSONDecodeError, RecursionError):
            raise IntegrationError("Integration response is invalid") from None
