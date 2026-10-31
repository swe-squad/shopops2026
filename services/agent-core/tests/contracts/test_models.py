import importlib

import pytest
from pydantic import ValidationError


def test_contracts_import_without_network_or_runtime_config():
    for name in ("identity", "models", "errors", "repository", "provider", "tools"):
        importlib.import_module(f"app.contracts.{name}")


def test_scope_and_snapshot_are_immutable():
    from app.contracts.identity import Scope
    from app.contracts.models import ConfigSnapshot

    scope = Scope(tenant_id="t", shop_id="s", user_id="u")
    with pytest.raises(ValidationError):
        scope.shop_id = "other"
    with pytest.raises(ValidationError):
        ConfigSnapshot(
            revision="r",
            template_id="t",
            model="m",
            knowledge_bundle="k",
            knowledge_version="1",
            mcp_profile="p",
            data_mcp_url="http://localhost",
            knowledge_mcp_url="http://localhost",
            capabilities=["a", "a"],
        )
