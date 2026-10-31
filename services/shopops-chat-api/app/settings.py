import json
import os
import re
from dataclasses import dataclass, field
from typing import Self
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


class CoreRoute(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    shop_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
    config_revision: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def demo_routes() -> dict[str, CoreRoute]:
    try:
        return TypeAdapter(dict[str, CoreRoute]).validate_python(
            json.loads(os.environ.get("AGENT_CORE_DEMO_ROUTES_JSON", "{}")), strict=True
        )
    except ValueError, TypeError:
        raise RuntimeError("Invalid AGENT_CORE_DEMO_ROUTES_JSON") from None


@dataclass(frozen=True)
class Settings:
    token: str
    api_key: str
    agent_id: str
    database: str

    backend: str = "openai_agents"
    auth_mode: str = "workspace_token"
    app_env: str = "production"
    core_url: str = ""
    core_shop: str = ""
    core_revision: str = ""
    shop_url: str = ""
    core_routes: dict[str, CoreRoute] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> Self:
        return cls(
            token=os.environ.get("SHOP_API_TOKEN", ""),
            api_key=os.environ.get("OPENAI_API_KEY", ""),
            agent_id=os.environ.get("OPENAI_ORCHESTRATOR_AGENT_ID", ""),
            database=os.environ.get("CHAT_DATA_PATH", "/data/chat.sqlite3"),
            backend=os.environ.get("CHAT_BACKEND", "openai_agents"),
            auth_mode=os.environ.get("CHAT_AUTH_MODE", "workspace_token"),
            app_env=os.environ.get("APP_ENV", "production"),
            core_url=os.environ.get("AGENT_CORE_URL", ""),
            core_shop=os.environ.get("AGENT_CORE_SHOP_ID", ""),
            core_revision=os.environ.get("AGENT_CORE_CONFIG_REVISION", ""),
            shop_url=os.environ.get("SHOPOPS_API_URL", ""),
            core_routes=demo_routes(),
        )

    def validate(self) -> None:
        if self.backend not in {"openai_agents", "agent_core"}:
            raise RuntimeError("Invalid CHAT_BACKEND")
        if self.backend == "agent_core":
            if self.auth_mode != "demo_phone" or self.app_env not in {"local", "test"}:
                raise RuntimeError("Core demo requires demo_phone and local/test")
            for name, value in (
                ("AGENT_CORE_URL", self.core_url),
                ("SHOPOPS_API_URL", self.shop_url),
            ):
                url = urlsplit(value)
                if (
                    url.scheme not in {"http", "https"}
                    or not url.hostname
                    or url.username
                    or url.password
                    or url.query
                    or url.fragment
                    or url.path not in {"", "/"}
                    or url.hostname.endswith(".cr.ngochoanielts.com")
                ):
                    raise RuntimeError(f"Invalid {name}")
            for value in (self.core_shop, self.core_revision):
                if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", value):
                    raise RuntimeError("Core shop/revision is required and must be an identifier")
            if not self.database.strip():
                raise RuntimeError("CHAT_DATA_PATH is required")
            return
        if self.auth_mode != "workspace_token":
            raise RuntimeError("Legacy backend requires workspace_token")
        for name, value in (
            ("SHOP_API_TOKEN", self.token),
            ("OPENAI_API_KEY", self.api_key),
            ("OPENAI_ORCHESTRATOR_AGENT_ID", self.agent_id),
            ("CHAT_DATA_PATH", self.database),
        ):
            if not value.strip():
                raise RuntimeError(f"{name} is required")
