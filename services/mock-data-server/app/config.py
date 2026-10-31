"""Runtime configuration; credentials never participate in repr or logs."""

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    host: str
    user: str
    password: str = field(repr=False)
    database: str
    port: int = 5432
    sslmode: str = "prefer"

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
        return cls(values["HOST"], values["USER"], values["PASSWORD"], values["DB"], port, sslmode)

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
