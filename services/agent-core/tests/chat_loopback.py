"""T09 loopback fixture: synthetic provider, never hosted proof."""

import ipaddress
import os
import socket
from pathlib import Path

from app.config.settings import Settings
from app.main import create_app
from tests.integration.test_hosted_workflow import FixtureTools, HostedFiles
from tests.integration.test_runtime import environment

original_connect = socket.socket.connect


def local_connect(sock, address):
    if sock.family in {socket.AF_INET, socket.AF_INET6}:
        host = address[0]
        if host != "localhost" and not ipaddress.ip_address(host).is_loopback:
            raise AssertionError("External network disabled in T09 fixture")
    return original_connect(sock, address)


socket.socket.connect = local_connect


class ChatBoundaryProvider(HostedFiles):
    """Model hosted environments only for hosted profiles, also exercise legacy rejection."""

    async def create_session(self, config, correlation_id, *, initial_input=None):
        result = await super().create_session(config, correlation_id, initial_input=initial_input)
        if config.runtime_profile.environment_type == "none":
            session = self._session(result.id)
            session.snapshot = session.snapshot.model_copy(update={"environment": None})
            result = result.model_copy(update={"environment": None})
        return result


provider = ChatBoundaryProvider()
app = create_app(
    settings=Settings.from_env(
        environment(Path(os.environ["T09_CORE_DATA"]))
        | {
            "CONFIG_PATH": "config/registry-hosted.example.json",
        }
    ),
    provider=provider,
    bridge=FixtureTools(),
)


@app.get("/_fixture/stats")
def stats() -> dict[str, int]:
    return {
        "sessions": len(provider.sessions),
        "turns": sum(s.turn_count for s in provider.sessions.values()),
    }


# Test-only controls, available only in this loopback fixture (never the runtime image).
@app.post("/_fixture/activate/{revision}")
async def activate(revision: str) -> dict[str, str]:
    from app.contracts.identity import Scope

    repository = app.state.repository
    if revision == "returns-hosted-v2":
        repository.registry.register(
            repository.registry.get("shopops", "returns-hosted-v1").model_copy(
                update={"revision": revision}
            )
        )
    await repository.activate_revision(
        Scope(tenant_id="tenant-a", user_id="alice", shop_id="shop-a"), "shopops", revision
    )
    return {"revision": revision}


@app.get("/_fixture/revisions")
def revisions() -> list[str]:
    return [session.config.revision for session in provider.sessions.values()]
