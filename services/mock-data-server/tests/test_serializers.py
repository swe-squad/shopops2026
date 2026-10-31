from app.domain.serialize_lazada import render as lazada
from app.domain.serialize_shopee import render as shopee
from app.domain.serialize_shopify import render as shopify
from app.domain.serialize_supplement import render as supplement
from tests.test_catalog import PRODUCT
from tests.test_orders import ITEM, ORDER
from tests.test_shops import SHOP


def test_shopee_native_quantity_and_discount_price():
    payload = shopee(SHOP, [ORDER], [ITEM])["orders"]
    order = payload["response"]["order_list"][0]
    assert order["order_sn"] == ORDER["order_id"]
    assert order["item_list"][0]["model_quantity_purchased"] == 2
    assert order["item_list"][0]["model_discounted_price"] == "100000.00"
    assert isinstance(order["create_time"], int)


def test_lazada_separate_unit_items():
    order = ORDER | {"shop_key": "lazada:1001", "original_status": "delivered"}
    item = ITEM | {"shop_key": "lazada:1001", "line_id": "100", "quantity": 1}
    documents = lazada(SHOP | {"platform": "lazada"}, [order], [item])
    assert documents["orders"]["data"]["orders"][0]["order_id"] == "100072"
    unit = documents["order_items"]["responses"][0]["data"][0]
    assert unit["order_item_id"] == "100"
    assert unit["item_price"] == "100000.00"
    assert unit["status"] == "delivered"


def test_shopify_preserves_global_ids_and_shipped_semantics():
    order = ORDER | {
        "order_id": "gid://shopify/Order/100072",
        "status": "shipped",
        "original_status": "FULFILLED",
    }
    item = ITEM | {"order_id": order["order_id"], "line_id": "gid://shopify/LineItem/100"}
    native = shopify(SHOP, [order], [item])["orders"]["data"]["orders"]["nodes"][0]
    assert native["id"] == order["order_id"]
    assert native["displayFulfillmentStatus"] == "FULFILLED"
    assert native["lineItems"]["nodes"][0]["quantity"] == 2
    assert native["lineItems"]["nodes"][0]["id"] == item["line_id"]
    assert native["cancelledAt"] is None


def test_supplement_retains_unknown_values_and_enrichment():
    result = supplement(SHOP, {"orders": [ORDER], "products": [PRODUCT | {"unit_cost": None}]})
    assert result["products"][0]["unit_cost"] is None
    assert result["order_enrichment"][0]["seller_discount"] == "0.00"
    assert "shop_key" not in result["products"][0]
    assert result["shop"]["capabilities"] == SHOP["capabilities"]
