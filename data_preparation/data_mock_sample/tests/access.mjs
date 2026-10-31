import assert from 'node:assert/strict';

export async function testAccess(db) {
  const query = async (sql, params = []) => (await db.query(sql, params)).rows;
  const shops = async userId => (await query(
    'SELECT shop_key FROM access.user_shop_access WHERE user_id=$1 ORDER BY shop_key',
    [userId],
  )).map(row => row.shop_key);
  const first = ['lazada:1001', 'shopee-open-platform:1001'];
  const second = ['shopee-open-platform:1002', 'shopify:1001'];
  let checks = 0;
  for (const [userId, expected] of [
    ['user-alice', first], ['user-bob', second],
    ['user-agency', [...first, ...second].sort()],
    ['user-revoked', []], ['user-disabled', []], ['user-unassigned', []],
    ['unknown-user', []], ['', []], [null, []], ["user-alice' OR true --", []],
  ]) {
    assert.deepEqual(await shops(userId), expected);
    checks++;
  }
  // Every existing business table can be scoped through the same shop relation.
  for (const table of ['shops', 'products', 'orders', 'order_items', 'reviews', 'returns',
    'inventory', 'promotions', 'settlements', 'fulfillment', 'account_health']) {
    const rows = await query(`SELECT DISTINCT t.shop_key FROM core.${table} t
      JOIN access.user_shop_access a USING (shop_key) WHERE a.user_id=$1`, ['user-alice']);
    assert.ok(rows.length > 0);
    assert.ok(rows.every(row => first.includes(row.shop_key)));
    checks++;
  }
  for (const view of ['order_economics', 'shop_daily', 'shop_window_metrics',
    'product_review_metrics', 'inventory_risk', 'promotion_performance', 'issue_candidates', 'agent_context']) {
    const rows = await query(`SELECT DISTINCT t.shop_key FROM mart.${view} t
      JOIN access.user_shop_access a USING (shop_key) WHERE a.user_id=$1`, ['user-alice']);
    assert.ok(rows.length > 0);
    assert.ok(rows.every(row => first.includes(row.shop_key)));
    checks++;
  }
  const raw = await query(`SELECT DISTINCT d.platform || ':' || d.shop_id AS shop_key
    FROM raw.documents d JOIN access.user_shop_access a
      ON a.platform=d.platform AND a.source_shop_id=d.shop_id AND a.merchant_id=d.merchant_id
    WHERE a.user_id=$1`, ['user-alice']);
  assert.deepEqual(raw.map(row => row.shop_key).sort(), first);
  checks++;
  for (const [userId, expected] of [['user-alice', 672], ['user-bob', 672],
    ['user-agency', 1344], ['user-revoked', 0]]) {
    const rows = await query(`SELECT count(*)::int AS orders FROM core.orders o
      JOIN access.user_shop_access a USING (shop_key) WHERE a.user_id=$1`, [userId]);
    assert.equal(rows[0].orders, expected);
    checks++;
  }
  for (const mutation of [
    "UPDATE access.merchant_memberships SET is_active=false WHERE user_id='user-alice'",
    "UPDATE access.users SET is_active=false WHERE user_id='user-alice'",
    "UPDATE access.merchants SET is_active=false WHERE merchant_id='merchant-demo-001'",
  ]) {
    await db.exec('BEGIN');
    try {
      await db.exec(mutation);
      assert.deepEqual(await shops('user-alice'), []);
      assert.deepEqual(await shops('user-bob'), second);
      assert.deepEqual(await shops('user-agency'), mutation.includes('access.merchants')
        ? second : [...first, ...second].sort());
    } finally { await db.exec('ROLLBACK'); }
    checks++;
  }
  const contexts = await query(`SELECT context FROM mart.agent_context`);
  const ownership = new Map((await query('SELECT shop_key,merchant_id FROM core.shops'))
    .map(row => [row.shop_key, row.merchant_id]));
  assert.ok(contexts.every(row => row.context.merchant_id === ownership.get(row.context.shop_key)));
  checks++;
  for (const sql of [
    "UPDATE core.shops SET merchant_id='unknown' WHERE shop_key='lazada:1001'",
    "UPDATE raw.documents SET merchant_id='merchant-demo-002' WHERE document_id='lazada/1001/supplement'",
    "INSERT INTO access.merchant_memberships VALUES ('unknown','merchant-demo-001','viewer',true)",
    "INSERT INTO access.merchant_memberships VALUES ('user-unassigned','merchant-demo-001','superadmin',true)",
    "INSERT INTO access.merchant_memberships VALUES ('user-alice','merchant-demo-001','viewer',true)",
  ]) {
    await assert.rejects(db.exec(sql));
    checks++;
  }
  return checks;
}
