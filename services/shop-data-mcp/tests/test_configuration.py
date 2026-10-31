import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from app.check import main
from app.main import create_app
from app.settings import Catalog, ConfigurationError, Settings


def test_missing_configuration_fails_startup(monkeypatch):
    monkeypatch.delenv("MCP_CONFIG_FILE", raising=False)
    with pytest.raises(RuntimeError, match="MCP_CONFIG_FILE"):
        create_app()


def test_placeholder_configuration_refuses_non_tls_database(monkeypatch, tmp_path):
    config = json.loads(Path("config.example.json").read_text())
    config["control_dsn"] = "host=localhost dbname=test sslmode=disable"
    target = tmp_path / "settings.json"
    target.write_text(json.dumps(config))
    monkeypatch.setenv("MCP_CONFIG_FILE", str(target))
    with pytest.raises(RuntimeError):
        Settings.load()


@pytest.fixture
def split_config(monkeypatch, tmp_path):
    config = json.loads(Path("config.example.json").read_text())
    catalog = json.loads(Path("catalog.example.json").read_text())
    operator_file = tmp_path / "operator.json"
    catalog_file = tmp_path / "catalog.json"
    operator_file.write_text(json.dumps(config))
    catalog_file.write_text(json.dumps(catalog))
    monkeypatch.setenv("MCP_CONFIG_FILE", str(operator_file))
    monkeypatch.setenv("MCP_CATALOG_FILE", str(catalog_file))
    return config, catalog, operator_file, catalog_file


def test_split_catalog_loads_metadata_without_overriding_shop_access(split_config):
    config, catalog, _, _ = split_config
    settings = Settings.load()
    assert settings.datasets == Catalog.model_validate(catalog).datasets
    shop = "shopee-open-platform:1001"
    assert settings.shops[shop].datasets == config["shops"][shop]["datasets"]


def test_legacy_inline_catalog_still_loads(split_config, monkeypatch):
    config, catalog, operator_file, _ = split_config
    config.update(catalog)
    operator_file.write_text(json.dumps(config))
    monkeypatch.delenv("MCP_CATALOG_FILE")
    assert len(Settings.load().datasets) == len(catalog["datasets"])


def test_ambiguous_catalog_sources_are_rejected(split_config):
    config, catalog, operator_file, _ = split_config
    config.update(catalog)
    operator_file.write_text(json.dumps(config))
    with pytest.raises(ConfigurationError, match="not both"):
        Settings.load()


def test_catalog_cannot_change_shop_credentials(split_config):
    _, catalog, _, catalog_file = split_config
    catalog["shops"] = {"other": {"query_dsn": "sensitive-value"}}
    catalog_file.write_text(json.dumps(catalog))
    with pytest.raises(ConfigurationError) as error:
        Settings.load()
    assert "extra_forbidden" in str(error.value)
    assert "sensitive-value" not in str(error.value)


def test_config_typo_is_reported_without_secret_values(split_config):
    config, _, operator_file, _ = split_config
    config["max_row"] = "do-not-print-this-value"
    operator_file.write_text(json.dumps(config))
    with pytest.raises(ConfigurationError) as error:
        Settings.load()
    assert "extra_forbidden" in str(error.value)
    assert "do-not-print-this-value" not in str(error.value)
    assert "password=" not in str(error.value)


def test_cronjob_runtime_url_and_separate_service_credential(split_config, monkeypatch):
    config, _, operator_file, _ = split_config
    config["ingestion_token"] = "test-service-credential"
    operator_file.write_text(json.dumps(config))
    monkeypatch.setenv("CRONJOB_SERVER_URL", "http://srv-captain--cronjob-server:8000")
    settings = Settings.load()
    assert settings.ingestion_url == "http://srv-captain--cronjob-server:8000"
    assert settings.ingestion_token.get_secret_value() == "test-service-credential"


@pytest.mark.parametrize("url", ["", "http://localhost:8001/path", "http://user:secret@localhost"])
def test_invalid_cronjob_origin_fails_startup(split_config, monkeypatch, url):
    config, _, operator_file, _ = split_config
    config["ingestion_token"] = "test-service-credential"
    operator_file.write_text(json.dumps(config))
    monkeypatch.setenv("CRONJOB_SERVER_URL", url)
    with pytest.raises(ConfigurationError):
        Settings.load()


def test_cronjob_url_without_service_token_fails_startup(split_config, monkeypatch):
    monkeypatch.setenv("CRONJOB_SERVER_URL", "http://localhost:8001")
    with pytest.raises(ConfigurationError):
        Settings.load()


def test_internal_url_is_explicit_runtime_configuration(split_config, monkeypatch):
    monkeypatch.setenv("MCP_INTERNAL_URL", "http://srv-captain--shop-data-mcp:8000/mcp")
    assert Settings.load().internal_url == "http://srv-captain--shop-data-mcp:8000/mcp"


@pytest.mark.parametrize(
    "url", ["http://*.example/mcp", "http://localhost/private", "http://u:p@host/mcp"]
)
def test_internal_transport_url_rejects_wildcards_paths_and_credentials(
    split_config, monkeypatch, url
):
    monkeypatch.setenv("MCP_INTERNAL_URL", url)
    with pytest.raises(ConfigurationError):
        Settings.load()


@pytest.mark.parametrize("time_column", [None, "not_exposed"])
def test_raw_catalog_requires_an_exposed_window_column(split_config, time_column):
    _, catalog, _, catalog_file = split_config
    raw = next(d for d in catalog["datasets"] if d["layer"] == "raw")
    raw["time_column"] = time_column
    catalog_file.write_text(json.dumps(catalog))
    with pytest.raises(ConfigurationError, match="datasets"):
        Settings.load()


def test_missing_catalog_and_unknown_shop_reference_fail_closed(split_config):
    _, _, _, catalog_file = split_config
    catalog_file.unlink()
    with pytest.raises(ConfigurationError):
        Settings.load()
    catalog_file.write_text('{"datasets":[]}')
    with pytest.raises(ConfigurationError, match="dataset mappings"):
        Settings.load()


@pytest.mark.parametrize(
    "name,model,sample",
    [
        ("config", Settings, "config.example.json"),
        ("catalog", Catalog, "catalog.example.json"),
    ],
)
def test_schema_export_needs_no_configuration_and_validates_example(
    monkeypatch, capsys, name, model, sample
):
    monkeypatch.delenv("MCP_CONFIG_FILE", raising=False)
    monkeypatch.delenv("MCP_CATALOG_FILE", raising=False)
    monkeypatch.setattr(sys, "argv", ["app.check", "--schema", name])
    main()
    exported = json.loads(capsys.readouterr().out)
    assert exported == model.model_json_schema()
    Draft202012Validator(exported).validate(json.loads(Path(sample).read_text()))
