"""Read-only deployment preflight; output contains no source records or identity."""

import argparse
import json

import httpx

from app.catalog import CatalogProvider, SourceCatalog
from app.catalog_models import CatalogSnapshot
from app.catalog_source import CatalogConfig, SourceNotFound, SourceUnavailable

PREFLIGHT_ERRORS = (SourceNotFound, SourceUnavailable)


def summary(
    status: str, shops: int = 0, products: int = 0, revision: int | None = None
) -> dict[str, str | int | None]:
    return {
        "status": status,
        "shops": shops,
        "products": products,
        "source_revision": revision,
    }


def check(provider: CatalogProvider) -> dict[str, str | int | None]:
    try:
        shops = provider.shops()
        products = 0
        for shop in shops.shops:
            catalog = provider.catalog(shop.shop_key)
            if not isinstance(catalog, CatalogSnapshot):
                raise SourceUnavailable()
            if catalog.source_revision != shops.source_revision:
                return summary("revision_changed")
            products += len(catalog.products)
        # Every shop is checked through the same authorized catalog path as the UI.
        return summary(
            "ready" if products else "empty", len(shops.shops), products, shops.source_revision
        )
    except PREFLIGHT_ERRORS:
        return summary("unavailable")


def main(
    argv: list[str] | None = None,
    *,
    provider: CatalogProvider | None = None,
    transport: httpx.BaseTransport | None = None,
) -> int:
    parser = argparse.ArgumentParser(description="Check catalog source with aggregate-only output")
    parser.add_argument(
        "--allow-empty", action="store_true", help="Accept a reachable source with zero products"
    )
    options = parser.parse_args(argv)
    if provider is None:
        try:
            config = CatalogConfig.from_environment()
        except RuntimeError:
            result = summary("invalid_configuration")
        else:
            result = (
                summary("disabled") if config is None else check(SourceCatalog(config, transport))
            )
    else:
        result = check(provider)
    print(json.dumps(result, separators=(",", ":")))
    if result["status"] == "ready" or (result["status"] == "empty" and options.allow_empty):
        return 0
    return 1 if result["status"] == "empty" else 2


if __name__ == "__main__":
    raise SystemExit(main())
