import json
from pathlib import Path

from app.auth.dependencies import Unauthorized
from app.contracts.identity import AuthContext


class FixtureAuthenticator:
    def __init__(self, *, app_env: str = "test", path: Path | None = None) -> None:
        if app_env not in {"test", "local"}:
            raise ValueError("fixture authentication requires local/test")
        source = path or Path(__file__).resolve().parents[2] / "fixtures/identities.json"
        self.identities = {
            token: AuthContext.model_validate(value)
            for token, value in json.loads(source.read_text()).items()
        }

    async def authenticate(self, token: str) -> AuthContext:
        try:
            return self.identities[token]
        except KeyError:
            raise Unauthorized() from None
