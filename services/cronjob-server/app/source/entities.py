"""Consumer-owned copy of the source entity contract; no source runtime imports."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    model_validator,
)

Text = Annotated[str, Field(min_length=1, max_length=500, pattern=r".*\S.*")]
Phone = Annotated[str, Field(pattern=r"^\+[1-9][0-9]{7,14}$")]
Money = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=2)]


def validate_image_url(value: str) -> str:
    url = HttpUrl(value)
    if url.scheme != "https" or url.username is not None or url.password is not None:
        raise ValueError("Image URL must use HTTPS without credentials")
    return value


ImageURL = Annotated[str, Field(max_length=2048), AfterValidator(validate_image_url)]


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")


class User(Record):
    user_id: Phone
    display_name: Text
    is_active: bool = True


class Merchant(Record):
    merchant_id: Text
    name: Text
    is_active: bool = True


class Membership(Record):
    user_id: Phone
    merchant_id: Text
    role: Literal["owner", "analyst", "viewer"]
    is_active: bool = True


class Shop(Record):
    shop_key: Text
    merchant_id: Text
    platform: Literal["shopee-open-platform", "lazada", "shopify"]
    source_shop_id: Text
    name: Text
    currency: Annotated[str, Field(pattern="^[A-Z]{3}$")]
    timezone: Text
    capabilities: dict[str, str | bool]

    @model_validator(mode="after")
    def validate_shop(self) -> Shop:
        if self.shop_key != f"{self.platform}:{self.source_shop_id}":
            raise ValueError("Shop key does not match platform and source ID")
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError:
            raise ValueError("Unknown timezone") from None
        if self.platform == "shopify" and self.capabilities.get("account_health") not in {
            None,
            False,
            "unsupported",
        }:
            raise ValueError("Shopify account health is unsupported")
        return self


class Product(Record):
    shop_key: Text
    sku: Text
    name: Text
    unit_cost: Money | None
    cost_basis: Text
    image_url: ImageURL | None = None


class Promotion(Record):
    shop_key: Text
    promotion_id: Text
    name: Text
    funding: Literal["seller", "platform", "shared", "unknown"]
    starts_at: AwareDatetime
    ends_at: AwareDatetime

    @model_validator(mode="after")
    def valid_dates(self) -> Promotion:
        if self.ends_at <= self.starts_at:
            raise ValueError("Promotion end must follow start")
        return self


Status = Literal["open", "shipped", "completed", "cancelled", "mixed", "unknown"]


class Order(Record):
    shop_key: Text
    order_id: Text
    ordered_at: AwareDatetime
    updated_at: AwareDatetime
    currency: Annotated[str, Field(pattern="^[A-Z]{3}$")]
    status: Status
    original_status: Text
    seller_discount: Money | None
    platform_discount: Money | None
    promotion_id: Text | None = None

    @model_validator(mode="after")
    def valid_times(self) -> Order:
        if self.updated_at < self.ordered_at:
            raise ValueError("Order update precedes creation")
        return self


class OrderItem(Record):
    shop_key: Text
    order_id: Text
    line_id: Text
    sku: Text
    quantity: Annotated[int, Field(gt=0)]
    unit_price: Money
    status: Literal["open", "shipped", "completed", "cancelled", "unknown"]
    native_status: Text | None = None


class Review(Record):
    shop_key: Text
    review_id: Text
    order_id: Text
    sku: Text
    reviewed_at: AwareDatetime
    rating: Annotated[int, Field(ge=1, le=5)]
    body: Annotated[str, Field(max_length=10000)]


class Return(Record):
    shop_key: Text
    return_id: Text
    order_id: Text
    requested_at: AwareDatetime
    reason: Text
    status: Text
    refund_amount: Money


class Inventory(Record):
    shop_key: Text
    sku: Text
    location_id: Text
    observed_at: AwareDatetime
    available: Annotated[int, Field(ge=0)] | None


class Settlement(Record):
    shop_key: Text
    order_id: Text
    fee_amount: Money | None
    seller_shipping_cost: Money | None
    refund_amount: Money | None
    actual_payout: Annotated[Decimal, Field(max_digits=18, decimal_places=2)] | None
    paid_at: AwareDatetime | None


class Fulfillment(Record):
    shop_key: Text
    order_id: Text
    ship_by: AwareDatetime
    shipped_at: AwareDatetime | None
    deadline_basis: Text


class AccountHealth(Record):
    shop_key: Text
    event_id: Text
    occurred_at: AwareDatetime
    expires_at: AwareDatetime
    penalty_points: Annotated[int, Field(ge=0)]
    reason: Text

    @model_validator(mode="after")
    def valid_interval(self) -> AccountHealth:
        if self.expires_at <= self.occurred_at:
            raise ValueError("Penalty expiry must follow occurrence")
        if self.shop_key.startswith("shopify:"):
            raise ValueError("Shopify account health is unsupported")
        return self


@dataclass(frozen=True)
class Resource:
    name: str
    table: str
    model: type[Record]
    keys: tuple[str, ...]
    refs: tuple = ()
    admin: bool = False
    immutable: tuple[str, ...] = ()


RESOURCES = {
    "inventory": Resource(
        "inventory",
        "inventory",
        Inventory,
        ("shop_key", "sku", "location_id", "observed_at"),
        ((("shop_key", "sku"), "products", ("shop_key", "sku")),),
    ),
    "settlements": Resource(
        "settlements",
        "settlements",
        Settlement,
        ("shop_key", "order_id"),
        ((("shop_key", "order_id"), "orders", ("shop_key", "order_id")),),
    ),
    "fulfillment": Resource(
        "fulfillment",
        "fulfillment",
        Fulfillment,
        ("shop_key", "order_id"),
        ((("shop_key", "order_id"), "orders", ("shop_key", "order_id")),),
    ),
    "account-health": Resource(
        "account-health",
        "account_health",
        AccountHealth,
        ("shop_key", "event_id"),
        ((("shop_key",), "shops", ("shop_key",)),),
    ),
    "reviews": Resource(
        "reviews",
        "reviews",
        Review,
        ("shop_key", "review_id"),
        (
            (("shop_key", "order_id"), "orders", ("shop_key", "order_id")),
            (("shop_key", "sku"), "products", ("shop_key", "sku")),
        ),
    ),
    "returns": Resource(
        "returns",
        "returns",
        Return,
        ("shop_key", "return_id"),
        ((("shop_key", "order_id"), "orders", ("shop_key", "order_id")),),
    ),
    "orders": Resource(
        "orders",
        "orders",
        Order,
        ("shop_key", "order_id"),
        (
            (("shop_key",), "shops", ("shop_key",)),
            (("shop_key", "promotion_id"), "promotions", ("shop_key", "promotion_id")),
        ),
    ),
    "order-items": Resource(
        "order-items",
        "order_items",
        OrderItem,
        ("shop_key", "order_id", "line_id"),
        (
            (("shop_key", "order_id"), "orders", ("shop_key", "order_id")),
            (("shop_key", "sku"), "products", ("shop_key", "sku")),
        ),
    ),
    "products": Resource(
        "products",
        "products",
        Product,
        ("shop_key", "sku"),
        ((("shop_key",), "shops", ("shop_key",)),),
    ),
    "promotions": Resource(
        "promotions",
        "promotions",
        Promotion,
        ("shop_key", "promotion_id"),
        ((("shop_key",), "shops", ("shop_key",)),),
    ),
    "shops": Resource(
        "shops",
        "shops",
        Shop,
        ("shop_key",),
        ((("merchant_id",), "merchants", ("merchant_id",)),),
        immutable=("merchant_id", "platform", "source_shop_id"),
    ),
    "users": Resource("users", "users", User, ("user_id",), admin=True),
    "merchants": Resource("merchants", "merchants", Merchant, ("merchant_id",), admin=True),
    "merchant-memberships": Resource(
        "merchant-memberships",
        "merchant_memberships",
        Membership,
        ("user_id", "merchant_id"),
        ((("user_id",), "users", ("user_id",)), (("merchant_id",), "merchants", ("merchant_id",))),
        admin=True,
    ),
}
