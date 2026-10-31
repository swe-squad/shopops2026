import ipaddress
import os
import socket

import pytest


@pytest.fixture(autouse=True)
def offline_network(monkeypatch, request):
    if request.node.get_closest_marker("live") and os.environ.get("AGENT_CORE_LIVE") == "1":
        return
    original = socket.socket.connect

    def connect(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            host = address[0]
            if host != "localhost" and not ipaddress.ip_address(host).is_loopback:
                raise AssertionError("External network is disabled in offline tests")
        return original(sock, address)

    monkeypatch.setattr(socket.socket, "connect", connect)


@pytest.fixture
def scope():
    from app.contracts.identity import Scope

    return Scope(tenant_id="tenant-a", shop_id="shop-a", user_id="user-a")


@pytest.fixture
def registry():
    from app.config.registry import Registry

    return Registry.load("config/registry.json")


@pytest.fixture
def repo(tmp_path, registry):
    import asyncio

    from app.storage.database import Database
    from app.storage.repositories import SQLiteRepository

    database = Database(tmp_path / "test.db")
    asyncio.run(database.initialize())
    return SQLiteRepository(database, registry)
