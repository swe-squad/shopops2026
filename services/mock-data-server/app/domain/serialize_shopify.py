def render(shop: dict, orders: list[dict], items: list[dict]) -> dict:
    nodes = []
    for order in orders:
        currency = order["currency"]
        nodes.append(
            {
                "id": order["order_id"],
                "createdAt": order["ordered_at"],
                "updatedAt": order["updated_at"],
                "currencyCode": currency,
                "cancelledAt": order["updated_at"] if order["status"] == "cancelled" else None,
                "displayFulfillmentStatus": order["original_status"],
                "totalDiscountsSet": {
                    "shopMoney": {
                        "amount": order["seller_discount"],
                        "currencyCode": currency,
                    }
                },
                "lineItems": {
                    "nodes": [
                        {
                            "id": item["line_id"],
                            "sku": item["sku"],
                            "quantity": item["quantity"],
                            "originalUnitPriceSet": {
                                "shopMoney": {
                                    "amount": item["unit_price"],
                                    "currencyCode": currency,
                                }
                            },
                        }
                        for item in items
                        if item["order_id"] == order["order_id"]
                    ]
                },
            }
        )
    return {"orders": {"data": {"orders": {"nodes": nodes}}}}
