import pytest

from app.config import Settings


def test_required_configuration_is_checked(monkeypatch):
    for name in ("POSTGRES_HOST", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValueError, match="POSTGRES_HOST"):
        Settings.from_env()


def test_password_is_preserved_but_not_printed(monkeypatch):
    monkeypatch.delenv("POSTGRES_PORT", raising=False)
    for name, value in {
        "POSTGRES_HOST": "localhost",
        "POSTGRES_USER": "test",
        "POSTGRES_PASSWORD": "test:@ /?",
        "POSTGRES_DB": "shopops_test_config",
    }.items():
        monkeypatch.setenv(name, value)
    settings = Settings.from_env()
    assert settings.connection_kwargs()["password"] == "test:@ /?"
    assert "test:@ /?" not in repr(settings)
    assert settings.port == 5432


def test_invalid_port_rejected(monkeypatch):
    for name in ("POSTGRES_HOST", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"):
        monkeypatch.setenv(name, "test")
    monkeypatch.setenv("POSTGRES_PORT", "0")
    with pytest.raises(ValueError, match="POSTGRES_PORT"):
        Settings.from_env()
