"""The protected MCP endpoint accepts only explicitly configured service hosts."""

from starlette.testclient import TestClient

from app.main import create_app
from app.settings import Settings


def test_internal_agent_host_is_allowed_and_unconfigured_host_is_rejected(monkeypatch):
    settings = Settings(
        control_dsn="postgresql://unused",
        membership_dsn="postgresql://membership@localhost/test",
        public_url="https://mcp.test/mcp",
        internal_url="http://srv-captain--shop-data-mcp:8000/mcp",
        shops={},
    )
    monkeypatch.setattr(Settings, "load", lambda: settings)
    protected = create_app()
    # Check host protection in the real SDK HTTP transport; phone checks have their own
    # membership tests. No tool is invoked and no database dependency is replaced.
    with TestClient(protected.app) as client:
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "integration-test", "version": "1"},
            },
        }
        headers = {"Accept": "application/json, text/event-stream"}
        allowed = client.post(
            "http://srv-captain--shop-data-mcp:8000/mcp",
            json=body,
            headers=headers,
        )
        assert allowed.status_code == 200
        denied = client.post("http://untrusted.example/mcp", json=body, headers=headers)
        assert denied.status_code == 421
    # Adding the internal host does not remove authentication.
    with TestClient(create_app()) as client:
        assert (
            client.post(
                "http://srv-captain--shop-data-mcp:8000/mcp",
                json=body,
                headers=headers,
            ).status_code
            == 401
        )
