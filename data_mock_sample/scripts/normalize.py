"""Read raw documents, apply connector mappings, export core JSONL and PostgreSQL seed."""
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLATFORMS = ('shopee-open-platform', 'lazada', 'shopify')
TABLES = ('shops', 'products', 'orders', 'order_items', 'reviews', 'returns', 'inventory',
          'promotions', 'settlements', 'fulfillment', 'account_health')
KEYS = dict(shops=['shop_key'], products=['shop_key','sku'], orders=['shop_key','order_id'],
    order_items=['shop_key','order_id','line_id'], reviews=['shop_key','review_id'],
    returns=['shop_key','return_id'], inventory=['shop_key','sku','location_id','observed_at'],
    promotions=['shop_key','promotion_id'], settlements=['shop_key','order_id'],
    fulfillment=['shop_key','order_id'], account_health=['shop_key','event_id'])
STATUSES = {'COMPLETED':'completed','READY_TO_SHIP':'open','PROCESSED':'open',
    'SHIPPED':'shipped','CANCELLED':'cancelled','delivered':'completed','pending':'open',
    'packed':'open','ready_to_ship':'open','shipped':'shipped','canceled':'cancelled'}


def amount(value):
    if value is None:
        return None
    return str(Decimal(str(value)).quantize(Decimal('0.01')))


def order_key(platform, value):
    value = str(value)
    return f'gid://shopify/Order/{value}' if platform == 'shopify' and not value.startswith('gid:') else value


def normalize_shop(platform, documents):
    docs = {doc['resource']: doc for doc in documents}
    native = docs['orders']
    supplement = docs['supplement']
    source = supplement['payload']
    shop_key = f"{platform}:{native['shop_id']}"
    result = {table: [] for table in TABLES}
    result['shops'].append(dict(shop_key=shop_key, platform=platform, source_shop_id=native['shop_id'],
        **source['shop'], source_document_id=supplement['document_id']))
    enrichment = {order_key(platform, row['order_id']): row for row in source['order_enrichment']}
    if platform == 'shopee-open-platform':
        rows = native['payload']['response']['order_list']
    elif platform == 'lazada':
        rows = native['payload']['data']['orders']
    else:
        rows = native['payload']['data']['orders']['nodes']
    lazada_items = {}
    if platform == 'lazada':
        for response in docs['order_items']['payload']['responses']:
            for item in response['data']:
                lazada_items.setdefault(str(item['order_id']), []).append(item)
    for row in rows:
        if platform == 'shopee-open-platform':
            oid = row['order_sn']
            created, updated = [datetime.fromtimestamp(row[k], timezone.utc).isoformat()
                                for k in ('create_time','update_time')]
            original = row['order_status']
            status = STATUSES.get(original, 'unknown')
            lines = [dict(line_id=f"{i['item_id']}:{i['model_id']}", sku=i['model_sku'],
                quantity=i['model_quantity_purchased'], unit_price=amount(i['model_discounted_price']),
                status=status, source_document_id=native['document_id']) for i in row['item_list']]
            seller_discount = enrichment[oid]['seller_discount']
            platform_discount = enrichment[oid]['platform_discount']
            currency = row['currency']
        elif platform == 'lazada':
            oid = str(row['order_id'])
            created, updated = [datetime.strptime(row[k], '%Y-%m-%d %H:%M:%S %z').isoformat()
                                for k in ('created_at','updated_at')]
            items = lazada_items[oid]
            statuses = {STATUSES.get(i['status'], 'unknown') for i in items}
            status = next(iter(statuses)) if len(statuses) == 1 else 'mixed'
            original = ','.join(sorted({i['status'] for i in items}))
            lines = [dict(line_id=str(i['order_item_id']), sku=i['sku'], quantity=1,
                unit_price=amount(i['item_price']), status=STATUSES.get(i['status'],'unknown'),
                source_document_id=docs['order_items']['document_id']) for i in items]
            seller_discount, platform_discount = row['voucher_seller'], row['voucher_platform']
            currencies = {i['currency'] for i in items}
            if len(currencies) != 1:
                raise ValueError(f'Mixed currency order {oid}')
            currency = currencies.pop()
        else:
            oid = row['id']
            created, updated = row['createdAt'], row['updatedAt']
            original = row['displayFulfillmentStatus']
            # FULFILLED is shipped, not proof of delivery. Demo reviews/payouts are independent evidence.
            status = 'cancelled' if row['cancelledAt'] else {'FULFILLED':'shipped','UNFULFILLED':'open'}.get(original,'unknown')
            lines = [dict(line_id=i['id'], sku=i['sku'], quantity=i['quantity'],
                unit_price=amount(i['originalUnitPriceSet']['shopMoney']['amount']), status=status,
                source_document_id=native['document_id']) for i in row['lineItems']['nodes']]
            seller_discount = row['totalDiscountsSet']['shopMoney']['amount']
            platform_discount = enrichment[oid]['platform_discount']
            currency = row['currencyCode']
        if currency != source['shop']['currency']:
            raise ValueError('Fixture contract requires shop-currency money')
        result['orders'].append(dict(shop_key=shop_key, order_id=oid, ordered_at=created, updated_at=updated,
            currency=currency, status=status, original_status=original, seller_discount=amount(seller_discount),
            platform_discount=amount(platform_discount), promotion_id=enrichment[oid]['promotion_id'],
            enrichment_source_document_id=supplement['document_id'],
            source_document_id=native['document_id']))
        result['order_items'].extend(dict(shop_key=shop_key, order_id=oid, **line) for line in lines)
    for table in TABLES:
        if table in ('shops','orders','order_items'):
            continue
        for row in source[table]:
            row = dict(row)
            if 'order_id' in row:
                row['order_id'] = order_key(platform, row['order_id'])
            for field in ('unit_cost','fee_amount','seller_shipping_cost','refund_amount','actual_payout'):
                if field in row:
                    row[field] = amount(row[field])
            result[table].append(dict(shop_key=shop_key, **row, source_document_id=supplement['document_id']))
    return result


def sql_literal(value):
    if value is None:
        return 'NULL'
    if isinstance(value, bool):
        return 'TRUE' if value else 'FALSE'
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, dict)):
        value = json.dumps(value, ensure_ascii=False)
    return "'" + str(value).replace("'", "''") + "'"


def insert(schema, table, rows, keys):
    if not rows:
        return ''
    columns = list(rows[0])
    values = ',\n'.join('(' + ','.join(sql_literal(row[col]) for col in columns) + ')' for row in rows)
    updates = ','.join(f'{col}=EXCLUDED.{col}' for col in columns if col not in keys)
    return (f'INSERT INTO {schema}.{table} ({",".join(columns)}) VALUES\n{values}\n'
            f'ON CONFLICT ({",".join(keys)}) DO UPDATE SET {updates};\n')


def build():
    all_docs = []
    combined = {table: [] for table in TABLES}
    for platform in PLATFORMS:
        docs = [json.loads(path.read_text(encoding='utf-8')) for path in sorted((ROOT/platform/'raw').glob('*.json'))]
        all_docs.extend(docs)
        core = {table: [] for table in TABLES}
        for shop_id in sorted({doc['shop_id'] for doc in docs}):
            result = normalize_shop(platform, [doc for doc in docs if doc['shop_id'] == shop_id])
            for table, rows in result.items():
                core[table].extend(rows)
        out = ROOT/platform/'core'
        out.mkdir(parents=True, exist_ok=True)
        for table, rows in core.items():
            (out/f'{table}.jsonl').write_text(''.join(json.dumps(row, ensure_ascii=False)+'\n' for row in rows), encoding='utf-8')
            combined[table].extend(rows)
    manifest = json.loads((ROOT/'manifest.json').read_text(encoding='utf-8'))
    sql = "-- Generated by scripts/normalize.py. Upserts; does not remove historical rows.\nSET standard_conforming_strings = on;\n"
    sql += insert('raw', 'documents', all_docs, ['document_id'])
    for table, rows in combined.items():
        sql += insert('core', table, rows, KEYS[table])
    sql += insert('mart','settings', [dict(singleton=True, as_of=manifest['as_of'],
        recent_days=manifest['recent_days'], baseline_days=manifest['baseline_days'])], ['singleton'])
    generated = ROOT/'.generated'
    generated.mkdir(exist_ok=True)
    (generated/'seed.sql').write_text(sql, encoding='utf-8')
    print(f'Built {len(all_docs)} raw documents, {len(combined["orders"])} orders, {len(combined["order_items"])} lines.')


if __name__ == '__main__':
    build()
