TABLES = (
    "products",
    "reviews",
    "returns",
    "inventory",
    "promotions",
    "settlements",
    "fulfillment",
    "account_health",
)


def render(shop: dict, data: dict[str, list[dict]]) -> dict:
    result = {
        "shop": {k: shop[k] for k in ("name", "currency", "timezone", "capabilities")},
        "order_enrichment": [
            {
                k: order[k]
                for k in ("order_id", "seller_discount", "platform_discount", "promotion_id")
            }
            for order in data.get("orders", [])
        ],
    }
    for table in TABLES:
        result[table] = [
            {k: v for k, v in row.items() if k != "shop_key"} for row in data.get(table, [])
        ]
    return result
