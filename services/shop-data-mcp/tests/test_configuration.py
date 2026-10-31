import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from starlette.testclient import TestClient

from app.check import main
from app.main import create_app
from app.settings import Catalog, ConfigurationError, Settings

DEMO_ADMIN_PHONES = {
    "+84900000001",
    "+84900000002",
    "+84900000003",
    "+84900000004",
    "+84900000005",
    "+84900000006",
    "+84900000007",
    "+84900000008",
    "+84900000009",
    "+84900000010",
}


@pytest.fixture(autouse=True)
def clean_config_environment(monkeypatch):
    for key in (
        "MCP_CONFIG_FILE",
        "MCP_CONFIG_JSON",
        "MCP_CATALOG_FILE",
        "MCP_CATALOG_JSON",
        "MCP_CONTROL_DSN",
        "MCP_MEMBERSHIP_DSN",
        "MCP_SHOPS_JSON",
        "MCP_INTERNAL_URL",
        "CRONJOB_SERVER_URL",
        "INGESTION_TOKEN",
    ):
        monkeypatch.delenv(key, raising=False)


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
    assert settings.scopes == {"data:read"}
    assert "issuer" not in Settings.model_fields


def test_container_config_loads_runtime_credentials_and_starts_app(split_config, monkeypatch):
    config, catalog, _, _ = split_config
    monkeypatch.setenv("MCP_CONFIG_FILE", str(Path("config.container.json").resolve()))
    monkeypatch.setenv("MCP_CONTROL_DSN", config["control_dsn"])
    monkeypatch.setenv("MCP_MEMBERSHIP_DSN", config["membership_dsn"])
    monkeypatch.setenv("MCP_SHOPS_JSON", json.dumps(config["shops"]))
    monkeypatch.setenv("CRONJOB_SERVER_URL", "http://srv-captain--cronjob-server-dev:8000")
    monkeypatch.setenv("INGESTION_TOKEN", "test-runtime-only-token")
    settings = Settings.load()
    assert settings.control_dsn.get_secret_value() == config["control_dsn"]
    assert settings.membership_dsn.get_secret_value() == config["membership_dsn"]
    assert set(settings.shops) == set(config["shops"])
    assert settings.datasets == Catalog.model_validate(catalog).datasets
    assert settings.cronjob_admin_phones == DEMO_ADMIN_PHONES
    assert settings.scopes == {"data:read", "cronjob:read", "cronjob:write"}
    with TestClient(create_app()) as client:
        assert client.get("/health").json() == {"status": "ok"}


def test_container_config_requires_real_runtime_database_configuration(split_config, monkeypatch):
    monkeypatch.setenv("MCP_CONFIG_FILE", str(Path("config.container.json").resolve()))
    with pytest.raises(ConfigurationError) as error:
        Settings.load()
    for field in ("control_dsn", "membership_dsn", "shops"):
        assert f"{field} (missing)" in str(error.value)


def test_runtime_database_overrides_replace_config_values(split_config, monkeypatch):
    config, _, _, _ = split_config
    dsn = config["membership_dsn"]
    monkeypatch.setenv("MCP_CONTROL_DSN", dsn)
    monkeypatch.setenv(
        "MCP_SHOPS_JSON", json.dumps({"runtime-shop": next(iter(config["shops"].values()))})
    )
    settings = Settings.load()
    assert settings.control_dsn.get_secret_value() == dsn
    assert set(settings.shops) == {"runtime-shop"}


@pytest.mark.parametrize("key", ["MCP_CONTROL_DSN", "MCP_MEMBERSHIP_DSN"])
@pytest.mark.parametrize(
    "value", ["", "host=localhost password=private-test-password sslmode=disable"]
)
def test_runtime_database_overrides_cannot_disable_verified_tls(
    split_config, monkeypatch, key, value
):
    monkeypatch.setenv(key, value)
    with pytest.raises(ConfigurationError) as error:
        Settings.load()
    assert "private-test-password" not in str(error.value)


@pytest.mark.parametrize("value", ["", '{"secret":"private-test-value"', "[]", "null"])
def test_invalid_runtime_shop_configuration_does_not_leak_values(split_config, monkeypatch, value):
    monkeypatch.setenv("MCP_SHOPS_JSON", value)
    with pytest.raises(ConfigurationError) as error:
        Settings.load()
    assert "private-test-value" not in str(error.value)


def test_environment_json_and_token_enable_cronjob_without_json_mounts(split_config, monkeypatch):
    config, catalog, operator_file, catalog_file = split_config
    config["scopes"] = ["data:read", "cronjob:read", "cronjob:write"]
    for prefix, value, path in (
        ("MCP_CONFIG", config, operator_file),
        ("MCP_CATALOG", catalog, catalog_file),
    ):
        monkeypatch.delenv(f"{prefix}_FILE")
        monkeypatch.setenv(f"{prefix}_JSON", json.dumps(value))
        path.unlink()
    monkeypatch.setenv("INGESTION_TOKEN", "environment-service-token")
    monkeypatch.setenv("CRONJOB_SERVER_URL", "http://srv-captain--cronjob-server-dev:8000")
    settings = Settings.load()
    assert settings.scopes == {"data:read", "cronjob:read", "cronjob:write"}
    assert settings.ingestion_token.get_secret_value() == "environment-service-token"
    assert settings.datasets == Catalog.model_validate(catalog).datasets
    assert settings.cronjob_admin_phones == DEMO_ADMIN_PHONES
    assert set(settings.shops) == set(config["shops"])
    with TestClient(create_app()) as client:
        assert client.get("/health").json() == {"status": "ok"}


@pytest.mark.parametrize("prefix", ["MCP_CONFIG", "MCP_CATALOG"])
def test_file_and_json_sources_are_mutually_exclusive(split_config, monkeypatch, prefix):
    monkeypatch.setenv(f"{prefix}_JSON", "{}")
    with pytest.raises(ConfigurationError, match=f"Choose {prefix}_FILE or {prefix}_JSON"):
        Settings.load()


@pytest.mark.parametrize("prefix", ["MCP_CONFIG", "MCP_CATALOG"])
@pytest.mark.parametrize("value", ["", '{"secret":"do-not-print"', '["do-not-print"]', "null"])
def test_invalid_environment_json_has_safe_source_diagnostics(
    split_config, monkeypatch, prefix, value
):
    monkeypatch.delenv(f"{prefix}_FILE")
    monkeypatch.setenv(f"{prefix}_JSON", value)
    with pytest.raises(ConfigurationError, match=f"{prefix}_JSON") as error:
        Settings.load()
    assert "do-not-print" not in str(error.value)


@pytest.mark.parametrize("prefix", ["MCP_CONFIG", "MCP_CATALOG"])
def test_missing_mounted_file_has_safe_source_diagnostics(
    split_config, monkeypatch, tmp_path, prefix
):
    monkeypatch.setenv(f"{prefix}_FILE", str(tmp_path / "private-missing-file.json"))
    with pytest.raises(ConfigurationError, match=f"Cannot read {prefix}_FILE") as error:
        Settings.load()
    assert "private-missing-file" not in str(error.value)


def test_environment_fragment_reports_required_database_fields(monkeypatch):
    monkeypatch.setenv(
        "MCP_CONFIG_JSON",
        json.dumps(
            {
                "public_url": "https://mcp.example/mcp",
                "scopes": ["data:read"],
                "ingestion_token": "do-not-print",
                "cronjob_admin_phones": [],
            }
        ),
    )
    with pytest.raises(ConfigurationError) as error:
        Settings.load()
    for field in ("control_dsn", "membership_dsn", "shops"):
        assert f"{field} (missing)" in str(error.value)
    assert "do-not-print" not in str(error.value)


@pytest.mark.parametrize("token", ["environment-service-token", "", "   ", "invalid\ntoken"])
def test_environment_token_overrides_file_and_rejects_invalid_values(
    split_config, monkeypatch, token
):
    config, _, operator_file, _ = split_config
    config["ingestion_token"] = "old-service-token"
    operator_file.write_text(json.dumps(config))
    monkeypatch.setenv("CRONJOB_SERVER_URL", "http://localhost:8001")
    monkeypatch.setenv("INGESTION_TOKEN", token)
    if token == "environment-service-token":
        assert Settings.load().ingestion_token.get_secret_value() == token
    else:
        with pytest.raises(ConfigurationError):
            Settings.load()


@pytest.mark.parametrize("value", [None, "host=localhost sslmode=disable"])
def test_membership_connection_is_required_and_uses_verified_tls(split_config, value):
    config, _, operator_file, _ = split_config
    if value is None:
        config.pop("membership_dsn")
    else:
        config["membership_dsn"] = value
    operator_file.write_text(json.dumps(config))
    with pytest.raises(ConfigurationError):
        Settings.load()


@pytest.mark.parametrize("scopes", [[], ["data:refresh"], ["data:read", "admin"]])
def test_invalid_server_capabilities_fail_startup(split_config, scopes):
    config, _, operator_file, _ = split_config
    config["scopes"] = scopes
    operator_file.write_text(json.dumps(config))
    with pytest.raises(ConfigurationError):
        Settings.load()


@pytest.mark.parametrize("override", [None, [], ["+84900000002"]])
def test_demo_admin_default_can_be_disabled_or_replaced(split_config, override):
    config, _, operator_file, _ = split_config
    if override is None:
        config.pop("cronjob_admin_phones")
    else:
        config["cronjob_admin_phones"] = override
    operator_file.write_text(json.dumps(config))
    settings = Settings.load()
    assert settings.cronjob_admin_phones == (
        DEMO_ADMIN_PHONES if override is None else set(override)
    )
    assert settings.scopes == {"data:read"}


def test_cronjob_capabilities_require_integration_and_admin_allowlist_is_validated(split_config):
    config, _, operator_file, _ = split_config
    config["scopes"] += ["cronjob:read", "cronjob:write"]
    operator_file.write_text(json.dumps(config))
    with pytest.raises(ConfigurationError):
        Settings.load()
    config["ingestion_url"] = "http://localhost:8001"
    config["ingestion_token"] = "test-service-token"
    config["cronjob_admin_phones"] = ["+84900000001"]
    operator_file.write_text(json.dumps(config))
    assert Settings.load().cronjob_admin_phones == {"+84900000001"}
    config["cronjob_admin_phones"] = ["invalid-private-value"]
    operator_file.write_text(json.dumps(config))
    with pytest.raises(ConfigurationError) as error:
        Settings.load()
    assert "invalid-private-value" not in str(error.value)


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
