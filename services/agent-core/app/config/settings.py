import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse


def endpoint(value: str, name: str) -> str:
    try:
        parsed = urlparse(value)
        host = parsed.hostname
        if (
            parsed.scheme not in {"http", "https"}
            or not host
            or parsed.username
            or parsed.password
            or parsed.fragment
            or parsed.query
            or not parsed.port
            and parsed.netloc.endswith(":")
        ):
            raise ValueError
        if host in {"169.254.169.254", "metadata.google.internal", "metadata", "100.100.100.200"}:
            raise ValueError
    except ValueError:
        raise ValueError(f"Invalid {name}") from None
    return value


@dataclass(frozen=True)
class Settings:
    app_env: str
    agent_provider: str
    auth_mode: str
    database_path: Path
    config_path: str
    data_mcp_mode: str
    data_mcp_url: str
    knowledge_memory_mcp_url: str
    mcp_token_signing_key: str = field(repr=False)
    openai_api_key: str = field(default="", repr=False)
    shop_data_bindings_path: str = ""
    shop_data_mcp_url: str = ""
    openai_model: str = ""
    auth_jwks_url: str = ""
    auth_issuer: str = ""
    auth_audience: str = ""
    port: int = 8000
    run_timeout_seconds: int = 180
    recovery_timeout_seconds: int = 60
    mcp_timeout_seconds: int = 15
    max_tool_calls_per_run: int = 8
    max_concurrent_runs: int = 4
    history_retention_days: int = 30
    runtime_bundle_path: str = "runtime-bundles"

    @property
    def runtime_bundle_root(self) -> Path:
        service = Path(__file__).resolve().parents[2]
        path = Path(self.runtime_bundle_path)
        target = service / path
        if (
            not self.runtime_bundle_path.strip()
            or path.is_absolute()
            or ".." in path.parts
            or not target.is_dir()
            or target.is_symlink()
            or not target.resolve().is_relative_to(service)
        ):
            raise ValueError("Invalid RUNTIME_BUNDLE_PATH")
        return target

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        env = os.environ if env is None else env

        def require(name: str) -> str:
            value = env.get(name, "").strip()
            if not value:
                raise ValueError(f"Missing {name}")
            return value

        def choice(name: str, allowed: set[str]) -> str:
            value = require(name)
            if value not in allowed:
                raise ValueError(f"Invalid {name}")
            return value

        def number(name: str, default: int, maximum: int = 86400) -> int:
            try:
                value = int(env.get(name, str(default)))
                if not 1 <= value <= maximum:
                    raise ValueError
            except ValueError:
                raise ValueError(f"Invalid {name}") from None
            return value

        app_env = choice("APP_ENV", {"local", "test", "develop", "production"})
        provider = choice("AGENT_PROVIDER", {"fake", "openai_agents"})
        auth_mode = choice("AUTH_MODE", {"fixture", "jwt"})
        if app_env not in {"local", "test"}:
            if provider == "fake":
                raise ValueError("AGENT_PROVIDER=fake requires APP_ENV=local|test")
            if auth_mode == "fixture":
                raise ValueError("AUTH_MODE=fixture requires APP_ENV=local|test")
        api_key = require("OPENAI_API_KEY") if provider == "openai_agents" else ""
        model = require("OPENAI_MODEL") if provider == "openai_agents" else ""
        jwks = endpoint(require("AUTH_JWKS_URL"), "AUTH_JWKS_URL") if auth_mode == "jwt" else ""
        issuer = require("AUTH_ISSUER") if auth_mode == "jwt" else ""
        audience = require("AUTH_AUDIENCE") if auth_mode == "jwt" else ""
        database_url = require("DATABASE_URL")
        if not database_url.startswith("sqlite:///"):
            raise ValueError("Invalid DATABASE_URL")
        path = database_url.removeprefix("sqlite:///")
        if not path or path == ":memory:" or "?" in path:
            raise ValueError("Invalid DATABASE_URL")
        signing_key = require("MCP_TOKEN_SIGNING_KEY")
        if len(signing_key.encode()) < 32:
            raise ValueError("Invalid MCP_TOKEN_SIGNING_KEY")
        return cls(
            runtime_bundle_path=(
                require("RUNTIME_BUNDLE_PATH")
                if "RUNTIME_BUNDLE_PATH" in env
                else "runtime-bundles"
            ),
            shop_data_bindings_path=env.get("SHOP_DATA_BINDINGS_PATH", ""),
            shop_data_mcp_url=(
                endpoint(require("SHOP_DATA_MCP_URL"), "SHOP_DATA_MCP_URL")
                if "SHOP_DATA_MCP_URL" in env
                else ""
            ),
            app_env=app_env,
            agent_provider=provider,
            auth_mode=auth_mode,
            database_path=Path(path),
            config_path=require("CONFIG_PATH"),
            data_mcp_mode=choice("DATA_MCP_MODE", {"mock", "remote"}),
            data_mcp_url=endpoint(require("DATA_MCP_URL"), "DATA_MCP_URL"),
            knowledge_memory_mcp_url=endpoint(
                require("KNOWLEDGE_MEMORY_MCP_URL"), "KNOWLEDGE_MEMORY_MCP_URL"
            ),
            mcp_token_signing_key=signing_key,
            openai_api_key=api_key,
            openai_model=model,
            auth_jwks_url=jwks,
            auth_issuer=issuer,
            auth_audience=audience,
            port=number("PORT", 8000, 65535),
            run_timeout_seconds=number("RUN_TIMEOUT_SECONDS", 180),
            recovery_timeout_seconds=number("RECOVERY_TIMEOUT_SECONDS", 60),
            mcp_timeout_seconds=number("MCP_TIMEOUT_SECONDS", 15),
            max_tool_calls_per_run=number("MAX_TOOL_CALLS_PER_RUN", 8, 8),
            max_concurrent_runs=number("MAX_CONCURRENT_RUNS", 4, 4),
            history_retention_days=number("HISTORY_RETENTION_DAYS", 30, 3650),
        )
