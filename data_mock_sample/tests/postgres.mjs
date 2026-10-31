import { PGlite } from '@electric-sql/pglite';
import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';

const root = new URL('../', import.meta.url);
const read = path => readFile(new URL(path, root), 'utf8');
const db = new PGlite();
const query = async sql => (await db.query(sql)).rows;
const scalar = async sql => Object.values((await query(sql))[0])[0];
let checks = 0;
const check = (condition, message) => { assert.ok(condition, message); checks++; };
try {
  await db.exec('BEGIN');
  for (const file of ['sql/001_schema.sql','.generated/seed.sql','mart/002_views.sql']) {
    await db.exec(await read(file));
  }
  await db.exec('COMMIT');
  check(Number(await scalar('SELECT count(*) FROM core.orders'))===1344, 'All four shops loaded');
  check(Number(await scalar('SELECT count(*) FROM core.order_items'))===1400, 'Lazada unit expansion');
  check(Number(await scalar('SELECT count(*) FROM mart.shop_daily'))===56, '14 daily rows per shop, no join fanout');
  const before = await query('SELECT * FROM mart.agent_context ORDER BY issue_key');
  const counts = await query('SELECT shop_key,issue_type,count(*)::int AS count FROM mart.issue_candidates GROUP BY 1,2 ORDER BY 1,2');
  const expected = ['product_reviews','promotion_loss','cancellation_spike','return_spike','fee_spike',
    'payout_mismatch','low_stock','shipment_risk','account_health'];
  for (const platform of ['shopee-open-platform','lazada','shopify']) {
    const actual = counts.filter(r=>r.shop_key===`${platform}:1001`).map(r=>r.issue_type).sort();
    assert.deepEqual(actual,expected.filter(t=>t!=='account_health'||platform!=='shopify').sort());
    checks++;
  }
  check(counts.every(r=>r.shop_key!=='shopee-open-platform:1002'), 'Healthy shop has no issue candidates');
  check(Number(await scalar("SELECT count(*) FROM mart.order_economics WHERE payout_variance=-25000"))===6,
    'Exactly six injected payout discrepancies');
  const rates = await query("SELECT * FROM mart.shop_window_metrics WHERE shop_key='lazada:1001' AND period='recent'");
  check(Number(rates[0].orders)===48 && Number(rates[0].cancellation_rate)===0.25, 'Cancellation denominator counts orders, not units');
  check(Number(rates[0].effective_fee_rate)===0.15, 'Fee baseline uses weighted sales');
  check(Number(await scalar("SELECT gross_sales FROM mart.order_economics WHERE shop_key='lazada:1001' AND order_id='100000'"))===400000,
    'Two units count once each');
  check(Number(await scalar("SELECT contribution_margin FROM mart.order_economics WHERE shop_key='lazada:1001' AND order_id='100000'"))===92000,
    'Margin excludes platform-funded discount and does not double-count refunds');
  check(Number(await scalar('SELECT count(*) FROM core.orders o CROSS JOIN mart.settings s WHERE o.updated_at>s.as_of'))===0,
    'No future order state');
  check(Number(await scalar('SELECT count(*) FROM core.settlements o CROSS JOIN mart.settings s WHERE o.paid_at>s.as_of'))===0,
    'No future settlements');
  // Replaying source events is safe: identical fixture load cannot double-count.
  await db.exec(await read('.generated/seed.sql'));
  assert.deepEqual(await query('SELECT * FROM mart.agent_context ORDER BY issue_key'), before);
  checks++;
  // A missing cost must suppress profit claims for the whole order, even in mixed-SKU orders.
  await db.exec("BEGIN; UPDATE core.products SET unit_cost=NULL WHERE shop_key='lazada:1001' AND sku='SHIRT-M';");
  check(Number(await scalar("SELECT count(*) FROM mart.order_economics WHERE shop_key='lazada:1001' AND order_id='100000' AND contribution_margin IS NULL AND NOT financials_complete"))===1,
    'Unknown costs are not zero costs');
  await db.exec('ROLLBACK');
  // Missing/stale stock cannot become an out-of-stock claim.
  await db.exec("BEGIN; UPDATE core.inventory SET available=NULL WHERE shop_key='lazada:1001';");
  check(Number(await scalar("SELECT count(*) FROM mart.issue_candidates WHERE shop_key='lazada:1001' AND issue_type='low_stock'"))===0,
    'Unknown inventory suppresses low-stock alerts');
  await db.exec('ROLLBACK');
  await db.exec("BEGIN; UPDATE mart.settings SET as_of=as_of+interval '2 days';");
  check(Number(await scalar("SELECT count(*) FROM mart.issue_candidates WHERE issue_type='low_stock'"))===0,
    'Stale snapshots suppress low-stock alerts');
  await db.exec('ROLLBACK');
  await assert.rejects(db.exec("INSERT INTO core.order_items VALUES ('lazada:1001','DOES_NOT_EXIST','x','CAP',1,10,'open','lazada/1001/orders')"));
  checks++;
  const contexts = before.map(row=>row.context);
  await writeFile(new URL('mart/agent-context.jsonl',root),contexts.map(row=>JSON.stringify(row)).join('\n')+'\n');
  const report = {engine: await scalar('SELECT version()'),checks,orders:1344,order_lines:1400,
    issue_candidates:contexts.length,counts};
  await writeFile(new URL('mart/validation-report.json',root),JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify(report,null,2));
} finally {
  await db.close();
}
