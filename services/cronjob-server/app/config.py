"""Runtime configuration; credentials never participate in repr or logs."""

import os
from dataclasses import dataclass, field
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Settings:
    host: str
    user: str
    password: str = field(repr=False)
    database: str
    port: int = 5432
    sslmode: str = "prefer"
    source_url: str = ""
    interval: int = 0

    @classmethod
    def from_env(cls) -> Settings:
        values = {}
        for key in ("HOST", "USER", "PASSWORD", "DB"):
            name = f"POSTGRES_{key}"
            value = os.getenv(name)
            if not value:
                raise ValueError(f"{name} is required")
            values[key] = value
        try:
            port = int(os.getenv("POSTGRES_PORT", "5432"))
            if not 1 <= port <= 65535:
                raise ValueError()
        except ValueError:
            raise ValueError("POSTGRES_PORT must be between 1 and 65535") from None
        sslmode = os.getenv("POSTGRES_SSLMODE", "prefer")
        if sslmode not in {"disable", "allow", "prefer", "require", "verify-ca", "verify-full"}:
            raise ValueError("Invalid POSTGRES_SSLMODE")
        source_url = os.getenv("MOCK_DATA_SERVER_URL", "").rstrip("/")
        parts = urlsplit(source_url)
        if (
            parts.scheme not in {"http", "https"}
            or not parts.hostname
            or parts.username
            or parts.password
            or parts.query
            or parts.fragment
            or parts.path
        ):
            raise ValueError("MOCK_DATA_SERVER_URL must be an HTTP origin")
        try:
            interval = int(os.getenv("SYNC_INTERVAL_SECONDS", "0"))
            if interval < 0:
                raise ValueError()
        except ValueError:
            raise ValueError("SYNC_INTERVAL_SECONDS must be a nonnegative integer") from None
        return cls(
            values["HOST"],
            values["USER"],
            values["PASSWORD"],
            values["DB"],
            port,
            sslmode,
            source_url,
            interval,
        )

    def connection_kwargs(self) -> dict:
        return dict(
            host=self.host,
            user=self.user,
            password=self.password,
            dbname=self.database,
            port=self.port,
            sslmode=self.sslmode,
            connect_timeout=5,
        )
