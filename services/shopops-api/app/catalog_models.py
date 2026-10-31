"""Public catalog DTOs; source-only identity and cost metadata stay private."""

from typing import Literal

from pydantic import BaseModel


class Shop(BaseModel):
    shop_key: str
    name: str
    platform: str
    currency: str
    timezone: str


class Product(BaseModel):
    shop_key: str
    sku: str
    name: str
    image_url: str | None = None
    unit_cost: str | None
    currency: str
    available: int | None
    inventory_observed_at: str | None
    last_sold_price: str | None
    last_sold_at: str | None
    order_count: int
    review_count: int
    negative_review_count: int
    return_order_count: int


class Review(BaseModel):
    review_id: str
    order_id: str
    reviewed_at: str
    rating: int
    body: str


class Order(BaseModel):
    order_id: str
    ordered_at: str
    status: str
    quantity: int
    unit_price: str


class Return(BaseModel):
    return_id: str
    order_id: str
    requested_at: str
    reason: str
    status: str
    refund_amount: str


class ShopsSnapshot(BaseModel):
    shops: list[Shop]
    source_revision: int
    fetched_at: str


class CatalogSnapshot(BaseModel):
    shop: Shop
    products: list[Product]
    source_revision: int
    fetched_at: str
    data_mode: Literal["mock_source"] = "mock_source"


class ProductSnapshot(BaseModel):
    shop: Shop
    product: Product
    reviews: list[Review]
    orders: list[Order]
    returns: list[Return]
    source_revision: int
    fetched_at: str
    data_mode: Literal["mock_source"] = "mock_source"
