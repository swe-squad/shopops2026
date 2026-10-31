from datetime import datetime

from app.domain.platforms import LAZADA_NATIVE


def render(shop: dict, orders: list[dict], items: list[dict]) -> dict:
    native_orders, responses = [], []
    for order in orders:
        lines = [item for item in items if item["order_id"] == order["order_id"]]
        native_orders.append(
            {
                "order_id": order["order_id"],
                "created_at": datetime.fromisoformat(order["ordered_at"]).strftime(
                    "%Y-%m-%d %H:%M:%S %z"
                ),
                "updated_at": datetime.fromisoformat(order["updated_at"]).strftime(
                    "%Y-%m-%d %H:%M:%S %z"
                ),
                "statuses": order["original_status"].split(","),
                "voucher_seller": order["seller_discount"],
                "voucher_platform": order["platform_discount"],
            }
        )
        responses.append(
            {
                "code": "0",
                "data": [
                    {
                        "order_id": order["order_id"],
                        "order_item_id": item["line_id"],
                        "sku": item["sku"],
                        "item_price": item["unit_price"],
                        "currency": order["currency"],
                        "status": item.get("native_status") or LAZADA_NATIVE[item["status"]],
                    }
                    for item in lines
                ],
            }
        )
    return {
        "orders": {"code": "0", "data": {"orders": native_orders}},
        "order_items": {"responses": responses},
    }
