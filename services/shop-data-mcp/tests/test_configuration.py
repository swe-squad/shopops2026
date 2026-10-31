import pytest

from app.main import create_app
from app.settings import Settings


def test_missing_configuration_fails_startup(monkeypatch):
    monkeypatch.delenv("MCP_CONFIG_FILE", raising=False)
    with pytest.raises(RuntimeError, match="MCP_CONFIG_FILE"):
        create_app()


def test_placeholder_configuration_refuses_non_tls_database(monkeypatch, tmp_path):
    import json
    from pathlib import Path

    config = json.loads(Path("config.example.json").read_text())
    config["control_dsn"] = "host=localhost dbname=test sslmode=disable"
    target = tmp_path / "settings.json"
    target.write_text(json.dumps(config))
    monkeypatch.setenv("MCP_CONFIG_FILE", str(target))
    with pytest.raises(RuntimeError):
        Settings.load()
