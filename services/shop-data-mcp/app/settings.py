"""Validated operator contracts. Secrets are loaded only by the server."""

import json
import os
from pathlib import Path

from pydantic import BaseModel, Field, SecretStr, field_validator


class Dataset(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,62}$")
    relation: str = Field(pattern=r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")
    layer: str = Field(pattern="^(mart|raw)$")
    description: str
    columns: list[str] = Field(min_length=1)
    time_column: str | None = None
    resource: str | None = None
    semantics: dict = Field(default_factory=dict)

    @field_validator("columns")
    @classmethod
    def identifiers(cls, values: list[str]) -> list[str]:
        import re

        if len(values) != len(set(values)) or any(
            not re.fullmatch(r"[a-z][a-z0-9_]*", v) for v in values
        ):
            raise ValueError("Invalid or duplicate catalog column")
        return values


class Shop(BaseModel):
    query_dsn: SecretStr
    datasets: list[str]


class Settings(BaseModel):
    control_dsn: SecretStr
    issuer: str
    audience: str
    jwks_url: str
    public_url: str
    datasets: list[Dataset]
    shops: dict[str, Shop]
    query_timeout_ms: int = Field(default=10000, ge=100, le=60000)
    max_rows: int = Field(default=500, ge=1, le=10000)
    max_bytes: int = Field(default=1048576, ge=1024, le=10485760)
    ttl_seconds: int = Field(default=3600, ge=60, le=86400)
    workspace_bytes: int = Field(default=10485760, ge=1024)
    refresh_lookback_days: int = Field(default=30, ge=1, le=365)
    refresh_cooldown_seconds: int = Field(default=300, ge=1)
    ingestion_url: str | None = None
    ingestion_token: SecretStr | None = None
    approval_url: str | None = None
    approval_token: SecretStr | None = None

    @classmethod
    def load(cls) -> "Settings":
        # Mount outside the repository; never log validation inputs or DSNs.
        try:
            settings = cls.model_validate(
                json.loads(Path(os.environ["MCP_CONFIG_FILE"]).read_text())
            )
            from urllib.parse import urlparse

            from psycopg.conninfo import conninfo_to_dict

            urls = [settings.issuer, settings.audience, settings.jwks_url, settings.public_url]
            if any(urlparse(url).scheme != "https" for url in urls):
                raise ValueError("HTTPS identity endpoints required")
            dsns = [settings.control_dsn, *[s.query_dsn for s in settings.shops.values()]]
            for dsn in dsns:
                opts = conninfo_to_dict(dsn.get_secret_value())
                if opts.get("sslmode") != "verify-full" or not opts.get("sslrootcert"):
                    raise ValueError("Verified PostgreSQL TLS required")
            ids = [d.id for d in settings.datasets]
            if len(ids) != len(set(ids)) or any(
                not set(s.datasets).issubset(ids) for s in settings.shops.values()
            ):
                raise ValueError("Invalid catalog mapping")
            return settings
        except Exception:
            raise RuntimeError("Invalid or missing MCP_CONFIG_FILE") from None
