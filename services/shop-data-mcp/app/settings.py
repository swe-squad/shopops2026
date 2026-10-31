"""Validated operator contracts. Secrets are loaded only by the server."""

import json
import os
from pathlib import Path
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    ValidationError,
    field_validator,
    model_validator,
)


class ConfigurationError(RuntimeError):
    """Operator-safe configuration diagnostics without input values."""


def load_json_source(prefix: str, *, required: bool = False) -> dict | None:
    """Read one operator-owned source without exposing its contents or file path."""
    file_key, json_key = f"{prefix}_FILE", f"{prefix}_JSON"
    path, inline = os.environ.get(file_key), os.environ.get(json_key)
    if path is not None and inline is not None:
        raise ConfigurationError(f"Choose {file_key} or {json_key}, not both")
    if path is None and inline is None:
        if required:
            raise ConfigurationError(f"Set {file_key} or {json_key}")
        return None
    source = file_key if path is not None else json_key
    if path is not None:
        try:
            inline = Path(path).read_text()
        except (OSError, ValueError, UnicodeError):
            raise ConfigurationError(
                f"Cannot read {file_key}; check file mount and permissions"
            ) from None
    try:
        value = json.loads(inline)
    except (ValueError, TypeError):
        raise ConfigurationError(f"{source} must contain valid JSON") from None
    if not isinstance(value, dict):
        raise ConfigurationError(f"{source} must contain a JSON object")
    return value


class StrictConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Dataset(StrictConfiguration):
    id: str = Field(
        pattern=r"^[a-z][a-z0-9_]{0,62}$",
        description="Logical SQL name used by agents, independent of the physical relation",
    )
    relation: str = Field(
        pattern=r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$",
        description="PostgreSQL schema.table or schema.view, protected by database shop isolation",
    )
    layer: str = Field(pattern="^(mart|raw)$", description="Raw requires an owner-approved grant")
    description: str = Field(description="Concise discovery text; never include customer records")
    columns: list[str] = Field(
        min_length=1,
        description="Approved projected column names; excludes credentials/private fields",
    )
    time_column: str | None = Field(
        default=None,
        description="Required for raw; must be an approved column used for grant windows",
    )
    resource: str | None = Field(
        default=None,
        description="Collector resource name allowed for automatic refresh, if supported",
    )
    semantics: dict = Field(
        default_factory=dict,
        description="Grain, metric definitions, units, null semantics, joins and freshness",
    )

    @field_validator("columns")
    @classmethod
    def identifiers(cls, values: list[str]) -> list[str]:
        import re

        if len(values) != len(set(values)) or any(
            not re.fullmatch(r"[a-z][a-z0-9_]*", v) for v in values
        ):
            raise ValueError("Invalid or duplicate catalog column")
        return values

    @model_validator(mode="after")
    def raw_window_column(self) -> "Dataset":
        if self.layer == "raw" and self.time_column not in self.columns:
            raise ValueError("Raw datasets require time_column in the approved columns")
        if self.time_column is not None and self.time_column not in self.columns:
            raise ValueError("time_column must be an approved column")
        return self


class Catalog(StrictConfiguration):
    """Non-secret, version-controlled metadata edited by the data engineer."""

    datasets: list[Dataset] = Field(description="Approved non-secret dataset metadata")


class Shop(StrictConfiguration):
    query_dsn: SecretStr
    datasets: list[str]


class Settings(StrictConfiguration):
    control_dsn: SecretStr
    membership_dsn: SecretStr = Field(
        description="Read-only login to the authoritative access.user_shop_access view"
    )
    scopes: set[
        Literal[
            "data:read", "raw:request", "raw:read", "data:refresh", "cronjob:read", "cronjob:write"
        ]
    ] = Field(
        default_factory=lambda: {"data:read"},
        description="Server-controlled capabilities for phone callers; raw still needs approval",
    )
    public_url: str
    internal_url: str | None = Field(
        default=None, description="Explicit internal MCP URL allowed by transport host protection"
    )
    datasets: list[Dataset] = Field(default_factory=list)
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
    cronjob_admin_phones: set[str] = Field(
        default_factory=set,
        description="Operator allowlist for cronjob admin CRUD; also requires cronjob scopes",
    )
    approval_url: str | None = None
    approval_token: SecretStr | None = None

    @field_validator("cronjob_admin_phones")
    @classmethod
    def valid_admin_phones(cls, values: set[str]) -> set[str]:
        import re

        if any(not re.fullmatch(r"\+[1-9][0-9]{7,14}", value) for value in values):
            raise ValueError("Admin identities must be E.164 phone numbers")
        return values

    @field_validator("scopes")
    @classmethod
    def read_scope_required(cls, value: set[str]) -> set[str]:
        if "data:read" not in value:
            raise ValueError("data:read scope is required")
        return value

    @classmethod
    def load(cls) -> "Settings":
        # Operator secrets stay outside the repository and are never logged.
        try:
            raw = load_json_source("MCP_CONFIG", required=True)
            if "CRONJOB_SERVER_URL" in os.environ:
                raw["ingestion_url"] = os.environ["CRONJOB_SERVER_URL"]
            if "MCP_INTERNAL_URL" in os.environ:
                raw["internal_url"] = os.environ["MCP_INTERNAL_URL"]
            if "INGESTION_TOKEN" in os.environ:
                raw["ingestion_token"] = os.environ["INGESTION_TOKEN"]
            catalog_raw = load_json_source("MCP_CATALOG")
            if catalog_raw is not None:
                if "datasets" in raw:
                    raise ConfigurationError(
                        "Choose inline datasets or MCP_CATALOG_FILE/MCP_CATALOG_JSON, not both"
                    )
                catalog = Catalog.model_validate(catalog_raw)
                raw["datasets"] = [d.model_dump() for d in catalog.datasets]
            settings = cls.model_validate(raw)
            if (
                settings.ingestion_url is not None
                or settings.ingestion_token is not None
                or settings.scopes & {"cronjob:read", "cronjob:write"}
            ):
                from app.upstream import Upstream

                Upstream(
                    settings.ingestion_url,
                    settings.ingestion_token.get_secret_value()
                    if settings.ingestion_token
                    else None,
                )._configured_url()
            from urllib.parse import urlparse

            if settings.internal_url is not None:
                internal = urlparse(settings.internal_url)
                if (
                    internal.scheme not in {"http", "https"}
                    or not internal.hostname
                    or internal.username
                    or internal.password
                    or internal.query
                    or internal.fragment
                    or internal.path != "/mcp"
                    or "*" in internal.netloc
                ):
                    raise ValueError("Invalid internal MCP URL")

            from psycopg.conninfo import conninfo_to_dict

            if urlparse(settings.public_url).scheme != "https":
                raise ValueError("HTTPS public MCP endpoint required")
            dsns = [
                settings.control_dsn,
                settings.membership_dsn,
                *[s.query_dsn for s in settings.shops.values()],
            ]
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
        except ConfigurationError:
            raise
        except ValidationError as exc:
            # Field paths and error categories are useful; validation inputs can contain DSNs.
            fields = set(cls.model_fields) | set(Dataset.model_fields) | set(Shop.model_fields)
            errors = []
            for error in exc.errors(include_input=False, include_context=False, include_url=False)[
                :5
            ]:
                path = ".".join(
                    str(part) if isinstance(part, int) or part in fields else "<entry>"
                    for part in error["loc"]
                )
                detail = error["msg"] if error["type"] == "value_error" else error["type"]
                errors.append(f"{path or 'catalog'} ({detail})")
            raise ConfigurationError("Invalid configuration fields: " + "; ".join(errors)) from None
        except Exception:
            raise ConfigurationError(
                "Invalid configuration: check MCP_CONFIG_FILE/MCP_CONFIG_JSON, "
                "MCP_CATALOG_FILE/MCP_CATALOG_JSON, "
                "JSON syntax, HTTPS endpoints, verified PostgreSQL TLS and dataset mappings"
            ) from None
