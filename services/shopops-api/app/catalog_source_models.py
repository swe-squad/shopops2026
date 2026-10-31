"""Consumer-owned subset of cronjob's HTTP contract, without runtime imports."""

from decimal import Decimal
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, Field

Text = Annotated[str, Field(min_length=1, max_length=500, pattern=r".*\S.*")]
Money = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=2, allow_inf_nan=False)]
Count = Annotated[int, Field(strict=True, ge=0)]


class SourceShop(BaseModel):
    shop_key: Text
    name: Text
    platform: Text
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
    timezone: Text


class SourceProduct(BaseModel):
    shop_key: Text
    sku: Text
    name: Text
    unit_cost: Money | None
    image_url: str | None = None


class SourceInventory(BaseModel):
    shop_key: Text
    sku: Text
    location_id: Text
    observed_at: AwareDatetime
    available: Count | None


class SourceOrder(BaseModel):
    shop_key: Text
    order_id: Text
    ordered_at: AwareDatetime
    status: Text


class SourceOrderItem(BaseModel):
    shop_key: Text
    order_id: Text
    line_id: Text
    sku: Text
    quantity: Annotated[int, Field(strict=True, gt=0)]
    unit_price: Money
    status: Text


class SourceReview(BaseModel):
    shop_key: Text
    review_id: Text
    order_id: Text
    sku: Text
    reviewed_at: AwareDatetime
    rating: Annotated[int, Field(strict=True, ge=1, le=5)]
    body: Annotated[str, Field(max_length=10000)]


class SourceReturn(BaseModel):
    shop_key: Text
    return_id: Text
    order_id: Text
    requested_at: AwareDatetime
    reason: Text
    status: Text
    refund_amount: Money


class Pagination(BaseModel):
    limit: Annotated[int, Field(strict=True, ge=1, le=200)]
    offset: Count
    total: Count


class SourcePage(BaseModel):
    data: list[dict]
    source_revision: Count
    pagination: Pagination


RESOURCE_MODELS = {
    "shops": SourceShop,
    "products": SourceProduct,
    "inventory": SourceInventory,
    "orders": SourceOrder,
    "order-items": SourceOrderItem,
    "reviews": SourceReview,
    "returns": SourceReturn,
}

RESOURCE_KEYS = {
    "shops": ("shop_key",),
    "products": ("shop_key", "sku"),
    "inventory": ("shop_key", "sku", "location_id", "observed_at"),
    "orders": ("shop_key", "order_id"),
    "order-items": ("shop_key", "order_id", "line_id"),
    "reviews": ("shop_key", "review_id"),
    "returns": ("shop_key", "return_id"),
}
