"""Compose delivered T02/T03 modules while keeping unfinished MCP/live wiring explicit."""

from collections.abc import Awaitable, Callable

from fastapi import APIRouter

from app.api.router import build_api_router
from app.auth.fixture import FixtureAuthenticator
from app.auth.jwt import JWTAuthenticator
from app.config.settings import Settings
from app.contracts.provider import AgentProvider
from app.contracts.repository import Repository
from app.providers.fake import FakeProvider


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
