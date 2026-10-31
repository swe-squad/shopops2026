import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from generate import make_shop
from normalize import normalize_shop, sql_literal


class ConnectorTests(unittest.TestCase):
    def test_every_raw_document_and_shop_has_merchant_ownership(self):
        expected = {'shopee-open-platform': 'merchant-demo-001',
                    'lazada': 'merchant-demo-001', 'shopify': 'merchant-demo-002'}
        for platform, merchant_id in expected.items():
            docs = make_shop(platform, '1001', True)
            self.assertTrue(all(d.get('merchant_id') == merchant_id for d in docs))
            shop = normalize_shop(platform, docs)['shops'][0]
            self.assertEqual(shop['merchant_id'], merchant_id)
        control = normalize_shop('shopee-open-platform', make_shop('shopee-open-platform', '1002', False))
        self.assertEqual(control['shops'][0]['merchant_id'], 'merchant-demo-002')

    def test_missing_or_conflicting_raw_ownership_is_rejected(self):
        for invalid in (None, 'merchant-demo-002'):
            docs = make_shop('lazada', '1001', True)
            if invalid is None:
                docs[0].pop('merchant_id', None)
            else:
                docs[0]['merchant_id'] = invalid
            with self.assertRaisesRegex(ValueError, 'ownership'):
                normalize_shop('lazada', docs)

    def test_lazada_units_and_mixed_status(self):
        docs = make_shop('lazada', '1001', True)
        response = next(d for d in docs if d['resource']=='order_items')['payload']['responses'][0]
        self.assertEqual(len(response['data']), 2)
        response['data'][1]['status'] = 'canceled'
        core = normalize_shop('lazada', docs)
        first = core['orders'][0]
        self.assertEqual(first['status'], 'mixed')
        lines = [i for i in core['order_items'] if i['order_id']==first['order_id']]
        self.assertEqual(sum(i['quantity'] for i in lines), 2)
        self.assertEqual(len({i['line_id'] for i in lines}), 2)

    def test_unknown_status_is_not_completed(self):
        docs = make_shop('shopee-open-platform', '1001', True)
        docs[0]['payload']['response']['order_list'][0]['order_status'] = 'NEW_UNDOCUMENTED_STATUS'
        core = normalize_shop('shopee-open-platform', docs)
        self.assertEqual(core['orders'][0]['status'], 'unknown')

    def test_shopify_gid_money_and_fulfillment(self):
        core = normalize_shop('shopify', make_shop('shopify','1001', True))
        self.assertEqual(core['orders'][0]['order_id'], 'gid://shopify/Order/100000')
        self.assertEqual(core['orders'][0]['status'], 'shipped')
        self.assertEqual(core['orders'][0]['platform_discount'], '0.00')
        self.assertTrue(all(s['order_id'].startswith('gid://') for s in core['settlements']))

    def test_raw_is_not_mutated(self):
        docs = make_shop('lazada','1001',True)
        before = copy.deepcopy(docs)
        normalize_shop('lazada',docs)
        self.assertEqual(docs,before)

    def test_sql_quotes_review_content(self):
        self.assertEqual(sql_literal("Seller's shirt"), "'Seller''s shirt'")

    def test_reproducibility_and_shop_collision(self):
        a = make_shop('shopee-open-platform','1001',True)
        self.assertEqual(a,make_shop('shopee-open-platform','1001',True))
        b = make_shop('shopee-open-platform','1002',False)
        aa, bb = [normalize_shop('shopee-open-platform',d)['orders'][0] for d in (a,b)]
        self.assertEqual(aa['order_id'],bb['order_id'])
        self.assertNotEqual(aa['shop_key'],bb['shop_key'])


if __name__ == '__main__':
    unittest.main()
