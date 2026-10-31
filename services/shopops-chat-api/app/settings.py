import os
from dataclasses import dataclass
from typing import Self


@dataclass(frozen=True)
class Settings:
    token: str
    api_key: str
    agent_id: str
    database: str

    @classmethod
    def from_env(cls) -> Self:
        return cls(
            token=os.environ.get("SHOP_API_TOKEN", ""),
            api_key=os.environ.get("OPENAI_API_KEY", ""),
            agent_id=os.environ.get("OPENAI_ORCHESTRATOR_AGENT_ID", ""),
            database=os.environ.get("CHAT_DATA_PATH", "/data/chat.sqlite3"),
        )

    def validate(self) -> None:
        for name, value in (
            ("SHOP_API_TOKEN", self.token),
            ("OPENAI_API_KEY", self.api_key),
            ("OPENAI_ORCHESTRATOR_AGENT_ID", self.agent_id),
            ("CHAT_DATA_PATH", self.database),
        ):
            if not value.strip():
                raise RuntimeError(f"{name} is required")
