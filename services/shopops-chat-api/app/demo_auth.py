"""Public synthetic fixtures, restricted to explicitly configured local/test deployments."""

import hashlib
import json
import re
import secrets
import time
from pathlib import Path

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, field_validator


class PhoneInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    phone_number: str

    @field_validator("phone_number")
    @classmethod
    def normalize(cls, value: str) -> str:
        value = value.strip()
        if not re.fullmatch(r"\+[1-9][0-9]{7,14}", value):
            raise ValueError("Use international phone format")
        return value


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class DemoAuth:
    def __init__(self, store) -> None:
        self.store = store
        self.identities = json.loads(
            (Path(__file__).resolve().parents[1] / "fixtures/demo-identities.json").read_text()
        )

    def login(self, phone: str) -> dict:
        if phone not in self.identities:
            raise HTTPException(401, "Unauthorized")
        identity = self.identities[phone]
        token, expires = secrets.token_urlsafe(32), time.time() + 3600
        with self.store.connect() as db:
            db.execute(
                "INSERT INTO demo_sessions VALUES(?,?,?)",
                (digest(token), json.dumps(identity), expires),
            )
        from datetime import UTC, datetime

        return {
            "access_token": token,
            "expires_at": datetime.fromtimestamp(expires, UTC).isoformat(),
        }

    def resolve(self, token: str) -> dict:
        with self.store.connect() as db:
            row = db.execute(
                "SELECT identity FROM demo_sessions WHERE token_hash=? AND expires>?",
                (digest(token), time.time()),
            ).fetchone()
        if row is None:
            raise HTTPException(401, "Unauthorized")
        return {**json.loads(row[0]), "chat_session_id": digest(token)}

    def logout(self, token: str) -> None:
        with self.store.connect() as db:
            db.execute("DELETE FROM demo_sessions WHERE token_hash=?", (digest(token),))
