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
provider = HostedFiles()
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
