-- Runnable examples. In an application, bind $1 from the verified session phone.
PREPARE mock_list_user_shops(text) AS
SELECT shop_key, merchant_id, role, platform, source_shop_id, name
FROM access.user_shop_access
WHERE user_id = $1
ORDER BY shop_key;

EXECUTE mock_list_user_shops('+84900000001'); -- Alice: two shops
EXECUTE mock_list_user_shops('+84900000003'); -- Agency: four shops
EXECUTE mock_list_user_shops('+84900000004'); -- Revoked: no shops
EXECUTE mock_list_user_shops('+84900000005'); -- Disabled: no shops
EXECUTE mock_list_user_shops('+84900000006'); -- Unassigned: no shops
EXECUTE mock_list_user_shops(NULL);           -- No identity: no shops
DEALLOCATE mock_list_user_shops;

PREPARE mock_list_orders(text, text) AS
SELECT o.*
FROM core.orders o
JOIN access.user_shop_access a USING (shop_key)
WHERE a.user_id = $1 AND o.shop_key = $2
ORDER BY o.ordered_at, o.order_id;

EXECUTE mock_list_orders('+84900000001', 'lazada:1001');  -- Four orders
EXECUTE mock_list_orders('+84900000001', 'shopify:1001'); -- No access
DEALLOCATE mock_list_orders;

PREPARE mock_list_products(text, text) AS
SELECT p.*
FROM core.products p
JOIN access.user_shop_access a USING (shop_key)
WHERE a.user_id = $1 AND p.shop_key = $2
ORDER BY p.sku;

EXECUTE mock_list_products('+84900000002', 'shopify:1001');
DEALLOCATE mock_list_products;

PREPARE mock_source_document(text, text) AS
SELECT d.*
FROM raw.documents d
JOIN access.user_shop_access a
  ON a.platform = d.platform AND a.source_shop_id = d.shop_id
 AND a.merchant_id = d.merchant_id
WHERE a.user_id = $1 AND d.document_id = $2;

EXECUTE mock_source_document('+84900000001', 'lazada/1001/orders');
DEALLOCATE mock_source_document;
