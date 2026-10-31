from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Self, cast

from app import catalog_models as dto
from app.catalog_source import SourceReader, SourceUnavailable
from app.catalog_source_models import (
    SourceInventory,
    SourceOrder,
    SourceOrderItem,
    SourceProduct,
    SourceReturn,
    SourceReview,
    SourceShop,
)


def money(value: Decimal | None) -> str | None:
    return format(value, ".2f") if value is not None else None


@dataclass
class CatalogData:
    shop: SourceShop
    products: list[SourceProduct]
    inventory: dict[str, list[SourceInventory]]
    orders: dict[str, SourceOrder]
    items: dict[str, list[SourceOrderItem]]
    reviews: dict[str, list[SourceReview]]
    returns: dict[str, list[SourceReturn]]

    @classmethod
    def read(cls, reader: SourceReader, shop: SourceShop) -> Self:
        products = cast(list[SourceProduct], reader.list("products", shop.shop_key))
        inventory = cast(list[SourceInventory], reader.list("inventory", shop.shop_key))
        orders = cast(list[SourceOrder], reader.list("orders", shop.shop_key))
        items = cast(list[SourceOrderItem], reader.list("order-items", shop.shop_key))
        reviews = cast(list[SourceReview], reader.list("reviews", shop.shop_key))
        returns = cast(list[SourceReturn], reader.list("returns", shop.shop_key))
        skus, order_ids = {p.sku for p in products}, {o.order_id for o in orders}
        if (
            any(i.sku not in skus for i in inventory)
            or any(i.sku not in skus or i.order_id not in order_ids for i in items)
            or any(r.sku not in skus or r.order_id not in order_ids for r in reviews)
            or any(r.order_id not in order_ids for r in returns)
        ):
            raise SourceUnavailable()
        data = cls(
            shop,
            products,
            defaultdict(list),
            {order.order_id: order for order in orders},
            defaultdict(list),
            defaultdict(list),
            defaultdict(list),
        )
        for value in inventory:
            data.inventory[value.sku].append(value)
        for value in items:
            data.items[value.sku].append(value)
        for value in reviews:
            data.reviews[value.sku].append(value)
        for value in returns:
            data.returns[value.order_id].append(value)
        return data

    def product(self, source: SourceProduct) -> dto.Product:
        items, reviews = self.items[source.sku], self.reviews[source.sku]
        latest_by_location: dict[str, SourceInventory] = {}
        for observation in self.inventory[source.sku]:
            previous = latest_by_location.get(observation.location_id)
            if previous is None or observation.observed_at > previous.observed_at:
                latest_by_location[observation.location_id] = observation
        latest = list(latest_by_location.values())
        available = (
            sum(row.available for row in latest)
            if latest and all(row.available is not None for row in latest)
            else None
        )
        purchases = [
            item
            for item in items
            if item.status in {"open", "shipped", "completed"}
            and self.orders[item.order_id].status not in {"cancelled", "unknown"}
        ]
        last_sale = max(
            purchases,
            key=lambda item: (self.orders[item.order_id].ordered_at, item.order_id, item.line_id),
            default=None,
        )
        return dto.Product(
            shop_key=source.shop_key,
            sku=source.sku,
            name=source.name,
            image_url=source.image_url,
            unit_cost=money(source.unit_cost),
            currency=self.shop.currency,
            available=available,
            # A sum is only as fresh as its oldest contributing location observation.
            inventory_observed_at=min(row.observed_at for row in latest).isoformat()
            if latest
            else None,
            last_sold_price=money(last_sale.unit_price) if last_sale else None,
            last_sold_at=self.orders[last_sale.order_id].ordered_at.isoformat()
            if last_sale
            else None,
            order_count=len({item.order_id for item in items}),
            review_count=len(reviews),
            negative_review_count=sum(review.rating <= 2 for review in reviews),
            return_order_count=len(
                {item.order_id for item in items if self.returns[item.order_id]}
            ),
        )

    def detail(self, source: SourceProduct, revision: int, fetched_at: str) -> dto.ProductSnapshot:
        items = sorted(
            self.items[source.sku],
            key=lambda item: (self.orders[item.order_id].ordered_at, item.order_id, item.line_id),
            reverse=True,
        )
        order_ids = {item.order_id for item in items}
        reviews = sorted(
            self.reviews[source.sku], key=lambda row: (row.reviewed_at, row.review_id), reverse=True
        )
        returns = sorted(
            [row for order_id in order_ids for row in self.returns[order_id]],
            key=lambda row: (row.requested_at, row.return_id),
            reverse=True,
        )
        return dto.ProductSnapshot(
            shop=dto.Shop(**self.shop.model_dump()),
            product=self.product(source),
            reviews=[
                dto.Review(
                    review_id=row.review_id,
                    order_id=row.order_id,
                    reviewed_at=row.reviewed_at.isoformat(),
                    rating=row.rating,
                    body=row.body,
                )
                for row in reviews
            ],
            orders=[
                dto.Order(
                    order_id=item.order_id,
                    ordered_at=self.orders[item.order_id].ordered_at.isoformat(),
                    status=item.status,
                    quantity=item.quantity,
                    unit_price=money(item.unit_price),
                )
                for item in items
            ],
            returns=[
                dto.Return(
                    return_id=row.return_id,
                    order_id=row.order_id,
                    requested_at=row.requested_at.isoformat(),
                    reason=row.reason,
                    status=row.status,
                    refund_amount=money(row.refund_amount),
                )
                for row in returns
            ],
            source_revision=revision,
            fetched_at=fetched_at,
        )
