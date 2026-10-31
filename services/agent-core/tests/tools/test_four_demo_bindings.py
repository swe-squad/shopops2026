import asyncio

import pytest

from app.auth.fixture import FixtureAuthenticator
from app.config.registry import Registry
from app.tools.shop_bindings import Bindings


@pytest.mark.parametrize(
    "number,shop_key",
    [
        (1, "shopee-open-platform:1001"),
        (2, "shopee-open-platform:1002"),
        (3, "lazada:1001"),
        (4, "shopify:1001"),
    ],
)
def test_demo_credential_revision_binding_and_cross_owner_denial(number, shop_key):
    token = "local-alice" if number == 1 else f"local-demo-{number:03}"
    shop = "shop-a" if number == 1 else f"shop-demo-{number:03}"
    revision = (
        "returns-hosted-data-luna-dev-v1"
        if number == 1
        else f"returns-hosted-data-luna-shop{number:03}-dev-v1"
    )
    identity = asyncio.run(FixtureAuthenticator().authenticate(token))
    assert "orchestrator:provision" in identity.permissions
    assert shop in identity.shop_ids
    if number > 1:
        assert identity.shop_ids == {shop}
    registry = Registry.load("config/registry.shop-data.develop.example.json")
    bindings = Bindings.load("config/shop-data-bindings.example.json")
    snapshot = registry.get("shopops", revision)
    value = bindings.resolve(snapshot.shop_data_binding, identity.scope(shop))
    assert value.phone == f"+849000000{number:02}"
    assert value.shop_key == shop_key
    for other in range(1, 5):
        if other == number:
            continue
        other_revision = (
            "returns-hosted-data-luna-dev-v1"
            if other == 1
            else f"returns-hosted-data-luna-shop{other:03}-dev-v1"
        )
        with pytest.raises(ValueError, match="scope mismatch"):
            bindings.resolve(
                registry.get("shopops", other_revision).shop_data_binding, identity.scope(shop)
            )
