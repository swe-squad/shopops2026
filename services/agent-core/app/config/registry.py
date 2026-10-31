import json
from pathlib import Path

from app.contracts.errors import ConfigurationConflict, InvalidInput
from app.contracts.models import ConfigSnapshot


class Registry:
    def __init__(
        self,
        revisions: tuple[ConfigSnapshot, ...],
        approved_remote_profiles: frozenset[str] = frozenset(),
    ) -> None:
        self.approved_remote_profiles = approved_remote_profiles
        self._revisions: dict[tuple[str, str], ConfigSnapshot] = {}
        for revision in revisions:
            self.register(revision)

    @classmethod
    def load(cls, path: str) -> Registry:
        try:
            data = json.loads(Path(path).read_text())
            profiles = data.get("approved_remote_profiles", [])
            if not isinstance(profiles, list) or any(
                not isinstance(value, str) or not value.strip() for value in profiles
            ):
                raise ValueError
            return cls(
                tuple(ConfigSnapshot.model_validate(r) for r in data["revisions"]),
                frozenset(profiles),
            )
        except OSError, ValueError, KeyError, TypeError:
            raise ValueError("Invalid CONFIG_PATH") from None

    def register(self, snapshot: ConfigSnapshot) -> None:
        key = (snapshot.template_id, snapshot.revision)
        if key in self._revisions and self._revisions[key] != snapshot:
            raise ConfigurationConflict()
        self._revisions[key] = snapshot

    def get(self, template_id: str, revision: str) -> ConfigSnapshot:
        try:
            return self._revisions[(template_id, revision)]
        except KeyError:
            raise InvalidInput() from None

    def snapshots(self) -> tuple[ConfigSnapshot, ...]:
        return tuple(self._revisions.values())
