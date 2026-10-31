"""Deterministic, synthetic source documents. No network or third-party packages."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from access_data import merchant_for_shop

ROOT = Path(__file__).resolve().parents[1]
VN = timezone(timedelta(hours=7))
AS_OF = datetime(2026, 10, 31, tzinfo=VN)
PLATFORMS = ('shopee-open-platform', 'lazada', 'shopify')


def iso(value):
    return value.isoformat()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def document(platform, shop_id, resource, payload, kind):
    return dict(document_id=f'{platform}/{shop_id}/{resource}', platform=platform,
                shop_id=shop_id, merchant_id=merchant_for_shop(platform, shop_id),
                resource=resource, source_kind=kind,
                captured_at=iso(AS_OF), payload=payload)


def make_shop(platform, shop_id, incident):
    products = [dict(sku=sku, name=name, unit_cost=cost, cost_basis='seller_supplied_demo')
                for sku, name, cost in [('SHIRT-M', 'Áo thun cotton size M', 130000),
                                        ('CAP', 'Nón lưỡi trai', 45000),
                                        ('TOTE', 'Túi tote canvas', 120000)]]
    supplemental = dict(shop=dict(name=f'VN Demo {platform} {shop_id}', currency='VND',
                                  timezone='Asia/Ho_Chi_Minh', capabilities={
                                      'orders': 'api_subset' if platform != PLATFORMS[0] else 'provisional',
                                      'reviews': 'demo_supplement', 'finance': 'demo_supplement',
                                      'inventory': 'demo_supplement', 'costs': 'seller_supplied_demo',
                                      'account_health': 'unsupported' if platform == 'shopify' else 'demo_supplement'}),
                        products=products, reviews=[], returns=[], inventory=[], promotions=[],
                        settlements=[], fulfillment=[], account_health=[], order_enrichment=[])
    supplemental['promotions'] = [dict(promotion_id='SAVE90', name='Giảm 90k cho áo thun',
        funding='seller', starts_at=iso(AS_OF-timedelta(days=2)), ends_at=iso(AS_OF+timedelta(days=5)))]
    source_orders, source_items = [], []
    for day in range(14):
        for j in range(24):
            created = AS_OF - timedelta(days=14-day) + timedelta(hours=8, minutes=20*j)
            recent = incident and day >= 12
            order_id = str(100000 + day*24+j)  # Deliberately collides across shops/platforms.
            sku, price = [('SHIRT-M', 200000), ('CAP', 100000), ('TOTE', 250000)][j % 3]
            qty = 2 if j % 7 == 0 else 1
            status = 'completed'
            if (recent and j >= 18) or (not recent and j == 23):
                status = 'cancelled'
            elif recent and day == 13 and 14 <= j <= 17:
                status = 'open'
            discount = (90000 if recent and sku == 'SHIRT-M' else 10000) * qty
            platform_discount = 0 if platform == 'shopify' else 5000 * qty
            promotion = 'SAVE90' if recent and sku == 'SHIRT-M' else None
            gross = price * qty
            fee = gross * (15 if recent else 5) // 100
            returned = status == 'completed' and ((recent and j < 5) or (day == 3 and j == 0))
            refund = gross - discount - platform_discount if returned else 0
            shipping = 8000
            payout = gross - discount - fee - shipping - refund
            if recent and j == 8:
                payout -= 25000
            supplemental['order_enrichment'].append(dict(order_id=order_id,
                seller_discount=discount, platform_discount=platform_discount, promotion_id=promotion))
            if status == 'completed':
                supplemental['settlements'].append(dict(order_id=order_id, fee_amount=fee,
                    seller_shipping_cost=shipping, refund_amount=refund, actual_payout=payout,
                    paid_at=iso(created+timedelta(hours=7))))
                negative = (recent and sku == 'SHIRT-M') or (not recent and day % 4 == 0 and j == 0)
                supplemental['reviews'].append(dict(review_id=f'R{order_id}', order_id=order_id, sku=sku,
                    reviewed_at=iso(created+timedelta(hours=4)), rating=1 if negative else 5,
                    body=('Áo quá chật, size M nhỏ hơn bảng size.' if negative else 'Hàng đẹp, giao nhanh.')))
                if returned:
                    supplemental['returns'].append(dict(return_id=f'RT{order_id}', order_id=order_id,
                        requested_at=iso(created+timedelta(hours=6)), reason='Không vừa / đổi ý',
                        status='refunded', refund_amount=refund))
            supplemental['fulfillment'].append(dict(order_id=order_id,
                ship_by=iso(created+timedelta(hours=3 if status == 'open' else 24)),
                shipped_at=iso(created+timedelta(hours=1)) if status == 'completed' else None,
                deadline_basis='demo_policy_not_marketplace_SLA'))
            if platform == PLATFORMS[0]:
                source_orders.append(dict(order_sn=order_id, create_time=int(created.timestamp()),
                    update_time=int((created+timedelta(hours=7)).timestamp()), currency='VND',
                    order_status={'completed':'COMPLETED','cancelled':'CANCELLED','open':'READY_TO_SHIP'}[status],
                    item_list=[dict(item_id=100+j%3, model_id=200+j%3, model_sku=sku,
                        model_quantity_purchased=qty, model_original_price=price, model_discounted_price=price)]))
            elif platform == 'lazada':
                native_status = {'completed':'delivered','cancelled':'canceled','open':'pending'}[status]
                source_orders.append(dict(order_id=int(order_id), created_at=created.strftime('%Y-%m-%d %H:%M:%S %z'),
                    updated_at=(created+timedelta(hours=7)).strftime('%Y-%m-%d %H:%M:%S %z'),
                    statuses=[native_status], price=str(gross), voucher_seller=str(discount),
                    voucher_platform=str(platform_discount)))
                for unit in range(qty):
                    source_items.append(dict(order_id=int(order_id), order_item_id=int(order_id)*10+unit,
                        sku=sku, item_price=str(price), status=native_status, currency='VND'))
            else:
                money = lambda amount: dict(shopMoney=dict(amount=str(amount), currencyCode='VND'))
                source_orders.append(dict(id=f'gid://shopify/Order/{order_id}', createdAt=iso(created),
                    updatedAt=iso(created+timedelta(hours=7)), currencyCode='VND',
                    cancelledAt=iso(created+timedelta(minutes=30)) if status == 'cancelled' else None,
                    displayFinancialStatus='REFUNDED' if returned else 'PAID',
                    displayFulfillmentStatus='FULFILLED' if status == 'completed' else 'UNFULFILLED',
                    totalDiscountsSet=money(discount), discountCodes=[promotion] if promotion else [],
                    lineItems=dict(nodes=[dict(id=f'gid://shopify/LineItem/{order_id}0', sku=sku,
                        quantity=qty, originalUnitPriceSet=money(price))])))
                # Shopify discounts in this fixture are merchant-funded; no marketplace subsidy.
                supplemental['order_enrichment'][-1]['platform_discount'] = 0
    for product in products:
        for lag in [2, 0]:
            supplemental['inventory'].append(dict(sku=product['sku'], location_id='VN-HCM-1',
                observed_at=iso(AS_OF-timedelta(hours=1, days=lag)),
                available=(2 if incident and product['sku'] == 'SHIRT-M' and lag == 0 else 250)))
    if incident and platform != 'shopify':
        supplemental['account_health'].append(dict(event_id='P1', occurred_at=iso(AS_OF-timedelta(hours=6)),
            expires_at=iso(AS_OF+timedelta(days=30)), penalty_points=3, reason='Demo: late shipment warning'))
    if platform == PLATFORMS[0]:
        payload = dict(error='', message='', response=dict(order_list=source_orders))
        kind = 'provisional_api_subset'
    elif platform == 'lazada':
        payload = dict(code='0', data=dict(orders=source_orders))
        kind = 'api_subset'
    else:
        payload = dict(data=dict(orders=dict(nodes=source_orders,
            pageInfo=dict(hasNextPage=False, endCursor=None))))
        kind = 'api_subset'
    docs = [document(platform, shop_id, 'orders', payload, kind),
            document(platform, shop_id, 'supplement', supplemental, 'demo_supplement')]
    if platform == 'lazada':
        # Bundle of /order/items/get responses, one per order, outside the API payload.
        docs.append(document(platform, shop_id, 'order_items', dict(responses=[
            dict(code='0', data=[item for item in source_items if item['order_id'] == order['order_id']])
            for order in source_orders]), kind))
    return docs


def generate():
    for platform in PLATFORMS:
        docs = make_shop(platform, '1001', True)
        if platform == PLATFORMS[0]:
            docs += make_shop(platform, '1002', False)
        for doc in docs:
            write_json(ROOT/platform/'raw'/f"{doc['shop_id']}_{doc['resource']}.json", doc)
    write_json(ROOT/'manifest.json', dict(schema_version='1.1', as_of=iso(AS_OF),
        recent_days=2, baseline_days=12, currency='VND', days=14, orders_per_shop_per_day=24,
        shops=4, users=6, merchants=2, merchant_memberships=6,
        access_model='active_merchant_membership', synthetic=True,
        time_compression='Same-day shipping/reviews/refunds/payouts for demo only'))


if __name__ == '__main__':
    generate()
    from normalize import build
    build()
