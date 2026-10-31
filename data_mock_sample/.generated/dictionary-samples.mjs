import { PGlite } from '@electric-sql/pglite';
import { readFile, writeFile } from 'node:fs/promises';
const root = new URL('../', import.meta.url);
const db = new PGlite();
try {
  for (const file of ['sql/001_schema.sql', '.generated/seed.sql', 'mart/002_views.sql']) {
    await db.exec(await readFile(new URL(file, root), 'utf8'));
  }
  const samples = {};
  for (const table of ['shops','products','orders','order_items','reviews','returns','inventory','promotions','settlements','fulfillment','account_health']) {
    samples[`core.${table}`] = (await db.query(`SELECT * FROM core.${table} WHERE shop_key='lazada:1001' ORDER BY ${table==='inventory' ? "observed_at DESC, sku DESC" : '1,2'} LIMIT 1`)).rows[0];
  }
  const queries = {
    'mart.settings': 'SELECT * FROM mart.settings',
    'mart.order_economics': "SELECT * FROM mart.order_economics WHERE shop_key='lazada:1001' AND order_id='100000'",
    'mart.shop_daily': "SELECT * FROM mart.shop_daily WHERE shop_key='shopee-open-platform:1001' ORDER BY business_date DESC LIMIT 1",
    'mart.shop_window_metrics': "SELECT * FROM mart.shop_window_metrics WHERE shop_key='shopee-open-platform:1001' AND period='recent'",
    'mart.product_review_metrics': "SELECT * FROM mart.product_review_metrics WHERE shop_key='shopee-open-platform:1001' AND sku='SHIRT-M' AND period='recent'",
    'mart.inventory_risk': "SELECT * FROM mart.inventory_risk WHERE shop_key='shopee-open-platform:1001' AND sku='SHIRT-M'",
    'mart.promotion_performance': "SELECT * FROM mart.promotion_performance WHERE shop_key='shopee-open-platform:1001'",
    'mart.issue_candidates': "SELECT * FROM mart.issue_candidates WHERE shop_key='shopee-open-platform:1001' AND issue_type='low_stock'",
    'mart.agent_context': "SELECT context FROM mart.agent_context WHERE shop_key='shopee-open-platform:1001' AND context->>'issue_type'='low_stock'",
  };
  for (const [name, sql] of Object.entries(queries)) samples[name] = (await db.query(sql)).rows[0];
  samples['mart.agent_context'] = samples['mart.agent_context'].context;
  await writeFile(new URL('.generated/dictionary-samples.json', root), JSON.stringify(samples,null,2));
  console.log(`Read example records for ${Object.keys(samples).length} tables/views.`);
} finally { await db.close(); }
