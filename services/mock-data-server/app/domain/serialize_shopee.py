from datetime import datetime


def render(shop: dict, orders: list[dict], items: list[dict]) -> dict:
    result = []
    for order in orders:
        lines = []
        for item in items:
            if item["order_id"] != order["order_id"]:
                continue
            item_id, model_id = map(int, item["line_id"].split(":"))
            lines.append(
                {
                    "item_id": item_id,
                    "model_id": model_id,
                    "model_sku": item["sku"],
                    "model_quantity_purchased": item["quantity"],
                    "model_original_price": item["unit_price"],
                    "model_discounted_price": item["unit_price"],
                }
            )
        result.append(
            {
                "order_sn": order["order_id"],
                "create_time": int(datetime.fromisoformat(order["ordered_at"]).timestamp()),
                "update_time": int(datetime.fromisoformat(order["updated_at"]).timestamp()),
                "currency": order["currency"],
                "order_status": order["original_status"],
                "item_list": lines,
            }
        )
    return {"orders": {"error": "", "message": "", "response": {"order_list": result}}}
