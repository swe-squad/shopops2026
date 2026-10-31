import pytest

from app.config import Settings


@pytest.fixture
def configured(monkeypatch):
    for key, value in {
        "POSTGRES_HOST": "localhost",
        "POSTGRES_USER": "demo",
        "POSTGRES_PASSWORD": "test-only",
        "POSTGRES_DB": "shopops_test_config",
        "MOCK_DATA_SERVER_URL": "http://localhost:8000",
        "SYNC_INTERVAL_SECONDS": "0",
    }.items():
        monkeypatch.setenv(key, value)


def test_source_url_is_required(configured, monkeypatch):
    monkeypatch.delenv("MOCK_DATA_SERVER_URL")
    with pytest.raises(ValueError, match="MOCK_DATA_SERVER_URL"):
        Settings.from_env()


@pytest.mark.parametrize("value", ["-1", "abc", "1.5"])
def test_invalid_interval(configured, monkeypatch, value):
    monkeypatch.setenv("SYNC_INTERVAL_SECONDS", value)
    with pytest.raises(ValueError, match="SYNC_INTERVAL_SECONDS"):
        Settings.from_env()


def test_credentials_are_hidden_and_interval_zero_disables(configured):
    settings = Settings.from_env()
    assert "test-only" not in repr(settings)
    assert settings.interval == 0
    assert settings.source_url == "http://localhost:8000"
