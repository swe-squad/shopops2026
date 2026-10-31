from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock
from typing import Annotated, Protocol, cast

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from app import catalog_models as dto
from app.catalog_data import CatalogData
from app.catalog_source import (
    CatalogConfig,
    RevisionChanged,
    SourceNotFound,
    SourceReader,
    SourceUnavailable,
)
from app.catalog_source_models import SourceShop
from app.contracts import AUTH_RESPONSES, ErrorDetail

Selection = Annotated[str, Query(min_length=1, max_length=500, pattern=r"^\S(?:.*\S)?$")]


class CatalogProvider(Protocol):
    def shops(self) -> dto.ShopsSnapshot: ...

    def catalog(
        self, shop_key: str, sku: str | None = None
    ) -> dto.CatalogSnapshot | dto.ProductSnapshot: ...


@dataclass(frozen=True)
class CachedCatalog:
    data: CatalogData
    revision: int
    fetched_at: str


class SourceCatalog:
    CACHE_SIZE = 8

    def __init__(self, config: CatalogConfig, transport: httpx.BaseTransport | None = None) -> None:
        self.config, self.transport = config, transport
        self._cache: OrderedDict[tuple[str, str, str], CachedCatalog] = OrderedDict()
        # One workspace: serialize checks/misses so polling cannot duplicate history fetches.
        self._lock = Lock()

    def _data(self, reader: SourceReader, shop: SourceShop) -> CachedCatalog:
        key = (self.config.base_url, self.config.user_id, shop.shop_key)
        cached = self._cache.pop(key, None)
        if cached is not None and cached.revision == reader.revision:
            self._cache[key] = cached
            return cached
        data = CatalogData.read(reader, shop)
        # A cache miss still requires a final current-access and coherent-revision check.
        if shop.shop_key not in {s.shop_key for s in reader.list("shops")}:
            raise SourceNotFound()
        cached = CachedCatalog(data, reader.revision, datetime.now(UTC).isoformat())
        self._cache[key] = cached
        while len(self._cache) > self.CACHE_SIZE:
            self._cache.popitem(last=False)
        return cached

    def _read(
        self, shop_key: str | None, sku: str | None = None
    ) -> dto.ShopsSnapshot | dto.CatalogSnapshot | dto.ProductSnapshot:
        with self._lock:
            return self._read_locked(shop_key, sku)

    def _read_locked(
        self, shop_key: str | None, sku: str | None
    ) -> dto.ShopsSnapshot | dto.CatalogSnapshot | dto.ProductSnapshot:
        for _attempt in range(3):
            try:
                with httpx.Client(
                    base_url=self.config.base_url,
                    transport=self.transport,
                    timeout=httpx.Timeout(30, connect=5),
                    follow_redirects=False,
                    trust_env=False,
                ) as client:
                    reader = SourceReader(client, self.config.user_id)
                    shops = cast(list[SourceShop], reader.list("shops"))
                    if shop_key is None:
                        return dto.ShopsSnapshot(
                            shops=[dto.Shop(**shop.model_dump()) for shop in shops],
                            source_revision=reader.revision,
                            fetched_at=datetime.now(UTC).isoformat(),
                        )
                    shop = next((shop for shop in shops if shop.shop_key == shop_key), None)
                    if shop is None:
                        raise SourceNotFound()
                    cached = self._data(reader, shop)
                    data, revision, fetched_at = cached.data, cached.revision, cached.fetched_at
                    if sku is not None:
                        product = next((p for p in data.products if p.sku == sku), None)
                        if product is None:
                            raise SourceNotFound()
                        return data.detail(product, revision, fetched_at)
                    return dto.CatalogSnapshot(
                        shop=dto.Shop(**shop.model_dump()),
                        products=[data.product(product) for product in data.products],
                        source_revision=revision,
                        fetched_at=fetched_at,
                    )
            except RevisionChanged:
                continue
        raise SourceUnavailable()

    def shops(self) -> dto.ShopsSnapshot:
        return cast(dto.ShopsSnapshot, self._read(None))

    def catalog(
        self, shop_key: str, sku: str | None = None
    ) -> dto.CatalogSnapshot | dto.ProductSnapshot:
        return cast(dto.CatalogSnapshot | dto.ProductSnapshot, self._read(shop_key, sku))


def router(authorize: Callable, provider: Callable[[], CatalogProvider | None]) -> APIRouter:
    api = APIRouter(
        prefix="/api/operations/catalog",
        dependencies=[Depends(authorize)],
        responses={
            **AUTH_RESPONSES,
            404: {"model": ErrorDetail, "description": "Selection is missing or inaccessible."},
            503: {"model": ErrorDetail, "description": "Catalog source is unavailable."},
        },
    )

    def read(
        shop_key: str | None = None, sku: str | None = None
    ) -> dto.ShopsSnapshot | dto.CatalogSnapshot | dto.ProductSnapshot:
        source = provider()
        if source is None:
            raise HTTPException(status_code=503, detail="Catalog source is not configured")
        try:
            return source.shops() if shop_key is None else source.catalog(shop_key, sku)
        except SourceNotFound:
            raise HTTPException(status_code=404, detail="Catalog selection not found") from None
        except SourceUnavailable:
            raise HTTPException(status_code=503, detail="Catalog source is unavailable") from None

    @api.get("/shops", response_model=dto.ShopsSnapshot)
    def shops() -> dto.ShopsSnapshot:
        return read()

    @api.get("", response_model=dto.CatalogSnapshot)
    def catalog(shop_key: Selection) -> dto.CatalogSnapshot:
        return read(shop_key)

    @api.get("/product", response_model=dto.ProductSnapshot)
    def product(shop_key: Selection, sku: Selection) -> dto.ProductSnapshot:
        return read(shop_key, sku)

    return api
