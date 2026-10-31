"""Consumer-owned cronjob-server CRUD contract (source entities and facade API).

Keep these wire models independent of the upstream service's runtime and database.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, create_model, model_validator

Text = Annotated[str, Field(min_length=1, max_length=500, pattern=r".*\S.*")]
Phone = Annotated[str, Field(pattern=r"^\+[1-9][0-9]{7,14}$")]
Money = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=2)]
IdempotencyKey = Annotated[str, Field(min_length=1, max_length=200, pattern=r"^[!-~]+$")]
Limit = Annotated[int, Field(ge=1, le=200)]
Offset = Annotated[int, Field(ge=0)]


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
    def valid_shop(self) -> "Shop":
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


class Promotion(Record):
    shop_key: Text
    promotion_id: Text
    name: Text
    funding: Literal["seller", "platform", "shared", "unknown"]
    starts_at: AwareDatetime
    ends_at: AwareDatetime

    @model_validator(mode="after")
    def valid_dates(self) -> "Promotion":
        if self.ends_at <= self.starts_at:
            raise ValueError("Promotion end must follow start")
        return self


class Order(Record):
    shop_key: Text
    order_id: Text
    ordered_at: AwareDatetime
    updated_at: AwareDatetime
    currency: Annotated[str, Field(pattern="^[A-Z]{3}$")]
    status: Literal["open", "shipped", "completed", "cancelled", "mixed", "unknown"]
    original_status: Text
    seller_discount: Money | None
    platform_discount: Money | None
    promotion_id: Text | None = None

    @model_validator(mode="after")
    def valid_times(self) -> "Order":
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
    def valid_interval(self) -> "AccountHealth":
        if self.expires_at <= self.occurred_at:
            raise ValueError("Penalty expiry must follow occurrence")
        if self.shop_key.startswith("shopify:"):
            raise ValueError("Shopify account health is unsupported")
        return self


@dataclass(frozen=True)
class Resource:
    name: str
    model: type[Record]
    keys: tuple[str, ...]
    admin: bool = False
    immutable: tuple[str, ...] = ()

    @property
    def path(self) -> str:
        return f"/v1/{'admin/' if self.admin else ''}mock/{self.name}"

    def key_model(self) -> type[Record]:
        return create_model(
            f"{self.model.__name__}Key",
            __base__=Record,
            **{k: (self.model.model_fields[k].rebuild_annotation(), ...) for k in self.keys},
        )

    def patch_model(self) -> type[Record]:
        return create_model(
            f"{self.model.__name__}Patch",
            __base__=Record,
            **{
                k: (f.rebuild_annotation() | None, None)
                for k, f in self.model.model_fields.items()
                if k not in (*self.keys, *self.immutable)
            },
        )


RESOURCES = (
    Resource("inventory", Inventory, ("shop_key", "sku", "location_id", "observed_at")),
    Resource("settlements", Settlement, ("shop_key", "order_id")),
    Resource("fulfillment", Fulfillment, ("shop_key", "order_id")),
    Resource("account-health", AccountHealth, ("shop_key", "event_id")),
    Resource("reviews", Review, ("shop_key", "review_id")),
    Resource("returns", Return, ("shop_key", "return_id")),
    Resource("orders", Order, ("shop_key", "order_id")),
    Resource("order-items", OrderItem, ("shop_key", "order_id", "line_id")),
    Resource("products", Product, ("shop_key", "sku")),
    Resource("promotions", Promotion, ("shop_key", "promotion_id")),
    Resource("shops", Shop, ("shop_key",), immutable=("merchant_id", "platform", "source_shop_id")),
    Resource("users", User, ("user_id",), admin=True),
    Resource("merchants", Merchant, ("merchant_id",), admin=True),
    Resource("merchant-memberships", Membership, ("user_id", "merchant_id"), admin=True),
)


class Pagination(BaseModel):
    limit: int
    offset: int
    total: int


class SourcePage[T](BaseModel):
    data: list[T]
    pagination: Pagination
    source_revision: int


class SourceResult[T](BaseModel):
    data: T
    source_revision: int


class Mutation[T](BaseModel):
    data: T | None
    source_revision: int | None
    mutation_status: Literal["pending", "applied", "unknown", "rejected"]
    run_id: UUID
    sync_status: str
    status_url: str


class SyncRun(BaseModel):
    run_id: UUID
    trigger: str
    status: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    attempts: int
    minimum_revision: int
    applied_revision: int | None
    mutation_status: str | None
    error_stage: str | None
    error_code: str | None
    shop_counts: dict[str, dict[str, int]]
