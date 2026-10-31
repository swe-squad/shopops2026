"""Compose delivered T02/T03 modules while keeping live wiring explicit."""

from collections.abc import Awaitable, Callable

from fastapi import APIRouter
from starlette.types import ASGIApp, Receive, Scope, Send

from app.api.router import build_api_router
from app.auth.fixture import FixtureAuthenticator
from app.auth.jwt import JWTAuthenticator
from app.config.registry import Registry
from app.config.settings import Settings
from app.contracts.provider import AgentProvider
from app.contracts.repository import Repository
from app.providers.fake import FakeProvider
from app.tools.bridge import MCPToolBridge
from app.tools.client import MCPClient
from app.tools.credentials import Credentials


def build_configured_router(
    repository: Repository, settings: Settings, readiness: Callable[[], Awaitable[bool]]
) -> APIRouter:
    if settings.auth_mode == "fixture":
        authenticator = FixtureAuthenticator(app_env=settings.app_env)
    else:
        authenticator = JWTAuthenticator(
            jwks_url=settings.auth_jwks_url,
            issuer=settings.auth_issuer,
            audience=settings.auth_audience,
        )
    return build_api_router(repository, authenticator.authenticate, readiness)


def build_offline_provider(settings: Settings) -> AgentProvider | None:
    # Live session creation is blocked on the shared contract amendment.
    # No automatic fallback from a requested live provider to simulated responses.
    if settings.agent_provider == "fake":
        if settings.app_env not in {"local", "test"}:
            raise ValueError("AGENT_PROVIDER=fake requires APP_ENV=local|test")
        return FakeProvider()
    return None


def build_configured_bridge(
    repository: Repository, registry: Registry, settings: Settings
) -> MCPToolBridge:
    snapshots = registry.snapshots()
    client = MCPClient(
        allowed_urls=frozenset(
            url
            for snapshot in snapshots
            for url in (snapshot.data_mcp_url, snapshot.knowledge_mcp_url)
        ),
        allow_loopback=settings.app_env in {"local", "test"},
        timeout_seconds=settings.mcp_timeout_seconds,
    )
    bridge = MCPToolBridge(
        repository=repository,
        credentials=Credentials(settings.mcp_token_signing_key),
        client=client,
        compatible_remote_profiles=registry.approved_remote_profiles,
        timeout_seconds=settings.mcp_timeout_seconds,
    )
    for snapshot in snapshots:
        bridge.validate_profile(snapshot)
    return bridge


def build_mcp_components(
    repository: Repository, registry: Registry, settings: Settings
) -> tuple[MCPToolBridge, dict[str, ASGIApp]]:
    from app.mcp.data import build_data_app
    from app.mcp.knowledge_memory import build_knowledge_memory_app

    bridge = build_configured_bridge(repository, registry, settings)
    credentials = Credentials(settings.mcp_token_signing_key)
    data = build_data_app(
        repository=repository, credentials=credentials, mode=settings.data_mcp_mode
    )
    mounts: dict[str, ASGIApp] = {
        "/mcp/knowledge-memory": build_knowledge_memory_app(
            repository=repository, credentials=credentials
        )
    }
    if data is not None:
        mounts["/mcp/data"] = data
    return bridge, mounts


class MCPExactEndpoint:
    """Dispatch a mounted MCP root without redirecting immutable slashless URLs."""

    def __init__(self, app: ASGIApp, prefix: str) -> None:
        self.app = app
        self.prefix = prefix

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        child_scope = dict(scope)
        child_scope["root_path"] = scope.get("root_path", "") + self.prefix
        child_scope["path"] = scope["path"] + "/"
        child_scope["raw_path"] = scope.get("raw_path", scope["path"].encode()) + b"/"
        await self.app(child_scope, receive, send)
