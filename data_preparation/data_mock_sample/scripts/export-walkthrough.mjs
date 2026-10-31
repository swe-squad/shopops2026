// Export real fixture records at each pipeline stage, using the shared PostgreSQL views.
import { PGlite } from '@electric-sql/pglite';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import assert from 'node:assert/strict';
import { expandWalkthrough } from './complete-samples.mjs';

const root = new URL('../', import.meta.url);
const output = new URL('examples/raw-to-mart/', root);
const platforms = ['shopee-open-platform', 'lazada', 'shopify'];
const selected = new Set(['100000', '100294']);
const selectedOrder = value => selected.has(String(value).split('/').at(-1));
const db = new PGlite();
const query = async (sql, parameters = []) => (await db.query(sql, parameters)).rows;
const save = async (name, data) => writeFile(new URL(name, output), JSON.stringify(data, null, 2) + '\n');

try {
  await mkdir(new URL('raw/', output), { recursive: true });
  for (const file of ['sql/001_schema.sql', '.generated/seed.sql', 'sql/003_access.sql', 'mart/002_views.sql']) {
    await db.exec(await readFile(new URL(file, root), 'utf8'));
  }
  for (const platform of platforms) {
    const documents = await query("SELECT * FROM raw.documents WHERE platform=$1 AND shop_id='1001' ORDER BY resource", [platform]);
    for (const document of documents) {
      const p = document.payload;
      if (document.resource === 'orders') {
        if (platform === 'shopee-open-platform') p.response.order_list = p.response.order_list.filter(o => selectedOrder(o.order_sn));
        else if (platform === 'lazada') p.data.orders = p.data.orders.filter(o => selectedOrder(o.order_id));
        else p.data.orders.nodes = p.data.orders.nodes.filter(o => selectedOrder(o.id));
      } else if (document.resource === 'order_items') {
        p.responses = p.responses.filter(response => selectedOrder(response.data[0].order_id));
      } else {
        for (const table of ['order_enrichment','reviews','returns','settlements','fulfillment']) {
          p[table] = p[table].filter(row => selectedOrder(row.order_id));
        }
        p.products = p.products.filter(row => row.sku === 'SHIRT-M');
        p.inventory = p.inventory.filter(row => row.sku === 'SHIRT-M');
      }
    }
    await save(`raw/${platform}.json`, {
      note: 'Selected excerpts from existing raw batches; original document IDs are preserved. Not complete API responses.',
      documents,
    });
  }

  const shopFilter = "shop_key IN ('shopee-open-platform:1001','lazada:1001','shopify:1001')";
  const orderFilter = "order_id IN ('100000','100294','gid://shopify/Order/100000','gid://shopify/Order/100294')";
  const core = {};
  for (const table of ['shops','products','orders','order_items','settlements','promotions']) {
    let filter = shopFilter;
    if (['orders','order_items','settlements'].includes(table)) filter += ` AND ${orderFilter}`;
    if (table === 'products') filter += " AND sku='SHIRT-M'";
    core[`core.${table}`] = await query(`SELECT * FROM core.${table} WHERE ${filter} ORDER BY 1,2${table === 'order_items' ? ',3' : ''}`);
  }
  const economics = await query(`SELECT * FROM mart.order_economics WHERE ${shopFilter} AND ${orderFilter} ORDER BY shop_key,order_id`);
  const promotion = await query(`SELECT * FROM mart.promotion_performance WHERE ${shopFilter} ORDER BY shop_key`);
  const contexts = (await query(`SELECT context FROM mart.agent_context WHERE ${shopFilter} AND context->>'issue_type'='promotion_loss' ORDER BY shop_key`)).map(row => row.context);

  assert.equal(core['core.orders'].length, 6);
  assert.equal(core['core.order_items'].length, 7);
  assert.equal(economics.length, 6);
  assert.equal(contexts.length, 3);
  for (const row of economics) {
    const baseline = row.order_id.endsWith('100000');
    assert.equal(Number(row.units), baseline ? 2 : 1);
    assert.equal(Number(row.contribution_margin), baseline ? 92000 : -58000);
    assert.equal(Number(row.payout_variance), 0);
  }
  await save('core.json', core);
  await save('mart.json', {
    scope: {
      order_economics: 'Only the six selected orders.',
      promotion_performance: 'Full 14-day dataset, filtered to the recent window by the shared SQL view. Not calculated from only these six orders.',
      agent_context: 'Full dataset promotion-loss candidates; minimum-sample rules still apply.',
    },
    'mart.order_economics': economics,
    'mart.promotion_performance': promotion,
    'mart.agent_context': contexts,
  });
  await expandWalkthrough(db, root, output);
} finally {
  await db.close();
}
