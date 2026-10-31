"""Bounded MCP Streamable HTTP client with JSON/SSE and DNS-pinned endpoints."""

import asyncio
import ipaddress
import json
import socket
from urllib.parse import urlsplit

import httpx

PROTOCOL_VERSION = "2025-06-18"
MAX_WIRE_BYTES = 256 * 1024
METADATA_HOSTS = frozenset({"metadata.google.internal", "metadata", "instance-data"})


class ClientError(Exception):
    def __init__(self, code: str, *, retryable: bool | None = None) -> None:
        self.code = code
        self.retryable = (
            code in {"timeout", "upstream_unavailable"} if retryable is None else retryable
        )
        super().__init__(code)


def _safe_ip(host: str, allow_loopback: bool) -> None:
    address = ipaddress.ip_address(host)
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    if (
        address.is_link_local
        or address.is_unspecified
        or address.is_multicast
        or str(address) == "fd00:ec2::254"
        or (address.is_loopback and not allow_loopback)
    ):
        raise ValueError("unsafe MCP endpoint")


def validate_url(url: str, *, allow_loopback: bool = False) -> None:
    try:
        parsed = urlsplit(url)
        host = parsed.hostname
        if (
            parsed.scheme not in {"http", "https"}
            or not host
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
            or parsed.query
            or any(c.isspace() for c in url)
            or "\\" in url
            or "%" in host
            or host.rstrip(".").lower() in METADATA_HOSTS
            or not parsed.port
            and parsed.netloc.endswith(":")
        ):
            raise ValueError("unsafe MCP endpoint")
        try:
            ipaddress.ip_address(host)
        except ValueError:
            if host.lower() == "localhost" and not allow_loopback:
                raise ValueError("loopback MCP endpoint is disabled") from None
        else:
            _safe_ip(host, allow_loopback)
    except TypeError, ValueError:
        raise ValueError("invalid MCP endpoint") from None


class MCPClient:
    def __init__(
        self,
        *,
        allowed_urls: frozenset[str],
        allow_loopback: bool = False,
        timeout_seconds: float = 15,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not allowed_urls or not 0 < timeout_seconds <= 15:
            raise ValueError("MCP client requires allowlisted URLs and timeout <=15 seconds")
        for url in allowed_urls:
            validate_url(url, allow_loopback=allow_loopback)
        self.allowed_urls = frozenset(allowed_urls)
        self.allow_loopback = allow_loopback
        self.timeout_seconds = timeout_seconds
        self._transport = transport

    def validate_endpoint(self, url: str) -> None:
        if url not in self.allowed_urls:
            raise ValueError("MCP endpoint not allowlisted")
        validate_url(url, allow_loopback=self.allow_loopback)

    async def _pin(self, url: str) -> httpx.URL:
        try:
            self.validate_endpoint(url)
        except ValueError:
            raise ClientError("invalid_input", retryable=False) from None
        parsed = httpx.URL(url)
        try:
            addresses = await asyncio.get_running_loop().getaddrinfo(
                parsed.host,
                parsed.port or (443 if parsed.scheme == "https" else 80),
                type=socket.SOCK_STREAM,
            )
        except OSError:
            raise ClientError("upstream_unavailable") from None
        if not addresses:
            raise ClientError("upstream_unavailable")
        # Check ALL answers, then connect directly to the checked numeric address.
        # Preserve original Host and TLS SNI; no second DNS lookup can rebind the target.
        try:
            for address in addresses:
                _safe_ip(address[4][0], self.allow_loopback)
        except ValueError:
            raise ClientError("invalid_input", retryable=False) from None
        return parsed.copy_with(host=addresses[0][4][0])

    async def _post(
        self,
        client: httpx.AsyncClient,
        url: httpx.URL,
        headers: dict,
        message: dict,
        original_host: str,
    ) -> tuple[dict | None, str | None]:
        async with client.stream(
            "POST", url, headers=headers, json=message, extensions={"sni_hostname": original_host}
        ) as response:
            if response.is_redirect:
                raise ClientError("invalid_input", retryable=False)
            if response.status_code in (401, 403):
                raise ClientError("permission_denied")
            if response.status_code == 404:
                raise ClientError("not_found")
            if response.status_code in (429, 500, 502, 503, 504):
                raise ClientError("upstream_unavailable")
            if response.status_code == 202 and "id" not in message:
                return None, response.headers.get("mcp-session-id")
            if response.status_code != 200:
                raise ClientError("upstream_unavailable", retryable=False)
            content_type = response.headers.get("content-type", "").split(";")[0]
            if content_type not in {"application/json", "text/event-stream"}:
                raise ClientError("upstream_unavailable", retryable=False)
            buffer = ""
            raw = bytearray()
            total = 0
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                if total > MAX_WIRE_BYTES:
                    raise ClientError("upstream_unavailable", retryable=False)
                raw.extend(chunk)
                if content_type == "text/event-stream":
                    # Decode complete lines only, so split UTF-8 code points remain valid.
                    while b"\n" in raw:
                        line, _, rest = raw.partition(b"\n")
                        raw = bytearray(rest)
                        text = line.decode("utf-8").rstrip("\r")
                        if text.startswith("data:"):
                            buffer += text[5:].lstrip(" ") + "\n"
                        elif not text and buffer:
                            event = json.loads(buffer)
                            buffer = ""
                            if isinstance(event, dict) and event.get("id") == message.get("id"):
                                return event, response.headers.get("mcp-session-id")
            if content_type == "application/json":
                value = json.loads(raw)
                if isinstance(value, dict):
                    return value, response.headers.get("mcp-session-id")
            raise ClientError("upstream_unavailable", retryable=False)

    @staticmethod
    def _result(message: dict | None, rpc_id: int) -> dict:
        if (
            not isinstance(message, dict)
            or message.get("jsonrpc") != "2.0"
            or type(message.get("id")) is not int
            or message["id"] != rpc_id
        ):
            raise ClientError("upstream_unavailable", retryable=False)
        if "error" in message:
            error = message["error"]
            text = error.get("message") if isinstance(error, dict) else None
            code = (
                text
                if text in {"invalid_input", "permission_denied", "not_found", "timeout"}
                else "upstream_unavailable"
            )
            raise ClientError(code, retryable=False)
        result = message.get("result")
        if not isinstance(result, dict):
            raise ClientError("upstream_unavailable", retryable=False)
        return result

    async def call_tool(self, url: str, token: str, name: str, arguments: dict) -> dict:
        deadline = asyncio.get_running_loop().time() + self.timeout_seconds
        try:
            async with asyncio.timeout(self.timeout_seconds):
                pinned = await self._pin(url)
                original = httpx.URL(url)
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json, text/event-stream",
                    "Host": original.netloc.decode(),
                    "MCP-Protocol-Version": PROTOCOL_VERSION,
                }
                async with httpx.AsyncClient(
                    timeout=self.timeout_seconds,
                    trust_env=False,
                    follow_redirects=False,
                    transport=self._transport,
                ) as client:
                    session = None
                    try:
                        initialized, proposed_session = await self._post(
                            client,
                            pinned,
                            headers,
                            {
                                "jsonrpc": "2.0",
                                "id": 1,
                                "method": "initialize",
                                "params": {
                                    "protocolVersion": PROTOCOL_VERSION,
                                    "capabilities": {},
                                    "clientInfo": {"name": "agent-core", "version": "1"},
                                },
                            },
                            original.host,
                        )
                        if proposed_session is not None:
                            if (
                                not proposed_session
                                or len(proposed_session) > 256
                                or any(not 33 <= ord(c) <= 126 for c in proposed_session)
                            ):
                                raise ClientError("upstream_unavailable", retryable=False)
                            session = proposed_session
                            headers["Mcp-Session-Id"] = session
                        result = self._result(initialized, 1)
                        if (
                            result.get("protocolVersion") != PROTOCOL_VERSION
                            or not isinstance(result.get("capabilities"), dict)
                            or "tools" not in result["capabilities"]
                        ):
                            raise ClientError("upstream_unavailable", retryable=False)
                        await self._post(
                            client,
                            pinned,
                            headers,
                            {"jsonrpc": "2.0", "method": "notifications/initialized"},
                            original.host,
                        )
                        reply, _ = await self._post(
                            client,
                            pinned,
                            headers,
                            {
                                "jsonrpc": "2.0",
                                "id": 2,
                                "method": "tools/call",
                                "params": {"name": name, "arguments": arguments},
                            },
                            original.host,
                        )
                        result = self._result(reply, 2)
                        value = result.get("structuredContent")
                        if value is None:
                            content = result.get("content")
                            if (
                                not isinstance(content, list)
                                or len(content) != 1
                                or not isinstance(content[0], dict)
                                or content[0].get("type") != "text"
                            ):
                                raise ClientError("upstream_unavailable", retryable=False)
                            value = json.loads(content[0]["text"])
                        if not isinstance(value, dict) or not isinstance(
                            result.get("isError", False), bool
                        ):
                            raise ClientError("upstream_unavailable", retryable=False)
                        if bool(result.get("isError", False)) != bool(value.get("error")):
                            raise ClientError("upstream_unavailable", retryable=False)
                        return value
                    finally:
                        # Best effort within the SAME total deadline. Never read a DELETE body.
                        # Cancellation/deadline exhaustion must propagate without extra delay.
                        remaining = deadline - asyncio.get_running_loop().time()
                        task = asyncio.current_task()
                        if session and remaining > 0 and task is not None and not task.cancelling():
                            try:
                                async with asyncio.timeout(min(1.0, remaining)):
                                    async with client.stream(
                                        "DELETE",
                                        pinned,
                                        headers=headers,
                                        extensions={"sni_hostname": original.host},
                                    ):
                                        pass
                            except httpx.HTTPError, TimeoutError:
                                # Remote servers must also expire abandoned sessions; cleanup
                                # transport failure must not replace the sanitized tool outcome.
                                pass
        except ClientError:
            raise
        except TimeoutError, httpx.TimeoutException:
            raise ClientError("timeout") from None
        except httpx.TransportError:
            raise ClientError("upstream_unavailable") from None
        except ValueError, TypeError, KeyError, AttributeError:
            raise ClientError("upstream_unavailable", retryable=False) from None
