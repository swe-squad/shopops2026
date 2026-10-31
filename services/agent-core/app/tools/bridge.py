"""Allowlisted read-only application tools; persistence belongs to the worker."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Protocol

from app.contracts.errors import CoreError
from app.contracts.identity import Scope
from app.contracts.models import ConfigSnapshot
from app.contracts.repository import Repository
from app.contracts.tools import PendingToolCall, ToolDefinition, ToolResult
from app.tools.client import ClientError, MCPClient, validate_url
from app.tools.credentials import Credentials, same_identity
from app.tools.shop_bindings import Bindings
from app.tools.shop_data import ShopDataAdapter
from app.tools.validation import (
    PERMISSIONS,
    definitions,
    validate_arguments,
    validate_context,
    validate_result,
)

PermissionResolver = Callable[[Scope, str], Awaitable[frozenset[str]]]
DATA_TOOLS = frozenset({"get_return_metrics", "get_review_summary"})


class ToolClient(Protocol):
    async def call_tool(self, url: str, token: str, name: str, arguments: dict) -> dict: ...


class MCPToolBridge:
    def __init__(
        self,
        *,
        repository: Repository,
        credentials: Credentials,
        permission_resolver: PermissionResolver | None = None,
        client: ToolClient,
        compatible_remote_profiles: frozenset[str] = frozenset(),
        timeout_seconds: float = 15,
        shop_data_bindings: Bindings | None = None,
    ) -> None:
        if not 0 < timeout_seconds <= 15:
            raise ValueError("MCP timeout must be in (0, 15]")
        self.shop_data_bindings = shop_data_bindings
        self.repository = repository
        self.credentials = credentials
        self.permission_resolver = permission_resolver
        self.client = client
        self.compatible_remote_profiles = frozenset(compatible_remote_profiles)
        self.timeout_seconds = timeout_seconds

    def validate_profile(self, config: ConfigSnapshot) -> None:
        if (
            config.mcp_profile != "mock-v1"
            and config.mcp_profile not in self.compatible_remote_profiles
        ):
            raise ValueError(
                "remote MCP profile requires explicit scoped-auth compatibility approval"
            )
        if config.mcp_profile == "shop-data-read-v1":
            if self.shop_data_bindings is None:
                raise ValueError("shop data bindings required")
            self.shop_data_bindings.get(config.shop_data_binding)
            if (
                isinstance(self.client, MCPClient)
                and config.data_mcp_url not in self.client.shop_data_urls
            ):
                raise ValueError("shop data transport policy missing")
        elif config.shop_data_binding is not None:
            raise ValueError("binding requires shop data profile")
        for url in (config.data_mcp_url, config.knowledge_mcp_url):
            validate_url(
                url,
                allow_loopback=(
                    self.client.allow_loopback
                    if isinstance(self.client, MCPClient)
                    else config.mcp_profile == "mock-v1"
                ),
            )
            if isinstance(self.client, MCPClient):
                self.client.validate_endpoint(url)

    def definitions(self, config: ConfigSnapshot) -> tuple[ToolDefinition, ...]:
        self.validate_profile(config)
        return tuple(d for d in definitions() if d.name in config.capabilities)

    async def execute(
        self, scope: Scope, conversation_id: str, config: ConfigSnapshot, call: PendingToolCall
    ) -> ToolResult:
        try:
            arguments = validate_arguments(call.name, call.arguments)
        except ValueError, TypeError:
            return ToolResult(error="invalid_input")
        if call.name not in config.capabilities:
            return ToolResult(error="permission_denied")
        try:
            self.validate_profile(config)
        except ValueError:
            return ToolResult(error="invalid_input")
        try:
            async with asyncio.timeout(self.timeout_seconds):
                conversation = await self.repository.get_conversation(scope, conversation_id)
                if not same_identity(conversation.scope, scope) or conversation.config != config:
                    return ToolResult(error="permission_denied")
                permissions = scope.permissions
                if self.permission_resolver is not None:
                    permissions = permissions & await self.permission_resolver(
                        scope, conversation_id
                    )
                if PERMISSIONS[call.name] not in permissions:
                    return ToolResult(error="permission_denied")
                is_data = call.name in DATA_TOOLS
                url = config.data_mcp_url if is_data else config.knowledge_mcp_url
                audience = "agent-core:data" if is_data else "agent-core:knowledge-memory"
                binding = None
                if is_data and config.mcp_profile == "shop-data-read-v1":
                    try:
                        binding = self.shop_data_bindings.resolve(config.shop_data_binding, scope)
                    except ValueError:
                        return ToolResult(error="permission_denied")
                for attempt in range(3):
                    token = self.credentials.issue(
                        scope, conversation_id, config.revision, audience, permissions
                    )
                    try:
                        if binding is not None:
                            value = await ShopDataAdapter(self.client).execute(
                                url, binding, call.name, arguments
                            )
                        else:
                            value = await self.client.call_tool(url, token, call.name, arguments)
                    except ClientError as exc:
                        if exc.retryable and attempt < 2:
                            await asyncio.sleep(0.05 * (2**attempt))
                            continue
                        return ToolResult(error=exc.code)
                    try:
                        result = validate_result(call.name, value)
                        validate_context(call.name, arguments, result, conversation_id, config)
                    except ValueError, KeyError, TypeError:
                        return ToolResult(error="upstream_unavailable")
                    if result.error in {"timeout", "upstream_unavailable"} and attempt < 2:
                        await asyncio.sleep(0.05 * (2**attempt))
                        continue
                    return result
        except TimeoutError:
            return ToolResult(error="timeout")
        except CoreError:
            return ToolResult(error="permission_denied")
        return ToolResult(error="upstream_unavailable")


def build_bridge(
    *,
    repository: Repository,
    credentials: Credentials,
    permission_resolver: PermissionResolver | None = None,
    client: ToolClient,
    compatible_remote_profiles: frozenset[str] = frozenset(),
    timeout_seconds: float = 15,
) -> MCPToolBridge:
    """Factory for T01; pass the shared repository and trusted permission resolver."""
    return MCPToolBridge(
        repository=repository,
        credentials=credentials,
        permission_resolver=permission_resolver,
        client=client,
        compatible_remote_profiles=compatible_remote_profiles,
        timeout_seconds=timeout_seconds,
    )
