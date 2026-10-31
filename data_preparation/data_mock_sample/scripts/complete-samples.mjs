import { readFile, writeFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
import { writeUseCaseGuides } from './use-case-guides.mjs';
import { exportAccess } from './export-access.mjs';

// Extract the source tables verbatim so dictionary additions are automatically included.
function sampleTables(markdown) {
  const lines = markdown.split(/\r?\n/);
  const tables = [];
  let section = '';
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].startsWith('#')) section = lines[i].replace(/^#+\s*/, '');
    if (!lines[i].startsWith('|') || !/\bExample\b|Illustrative example/i.test(lines[i])) continue;
    const table = [];
    while (i < lines.length && lines[i].startsWith('|')) table.push(lines[i++]);
    i--;
    tables.push({ section, markdown: table.join('\n'), rows: table.length - 2 });
  }
  assert.ok(tables.length, 'Dictionary sample tables must exist');
  return tables;
}

export async function expandWalkthrough(db, root, output) {
  const query = async (sql, parameters = []) => (await db.query(sql, parameters)).rows;
  const read = name => readFile(new URL(name, root), 'utf8');
  const save = (name, value) => writeFile(new URL(name, output), JSON.stringify(value, null, 2) + '\n');
  const fence = value => '```json\n' + JSON.stringify(value, null, 2) + '\n```';
  const baseId = value => String(value).split('/').at(-1);
  const platforms = ['shopee-open-platform', 'lazada', 'shopify'];
  const coreTables = ['shops','products','orders','order_items','reviews','returns','inventory',
    'promotions','settlements','fulfillment','account_health'];
  const martViews = ['order_economics','shop_daily','shop_window_metrics','product_review_metrics',
    'inventory_risk','promotion_performance','issue_candidates','agent_context'];
  const definitions = {
    product_reviews: ['Negative review spike and repeated sizing complaints', ['reviews'], ['product_review_metrics'], 'Compare post-change sizing-review rates for purchases exposed to the new listing after sufficient review delay.'],
    promotion_loss: ['Promotion associated with negative margins', ['orders','order_items','products','promotions','settlements'], ['order_economics','promotion_performance'], 'Compare settled contribution margin after the action using comparable SKU mix and enough orders.'],
    cancellation_spike: ['Cancellation-rate increase', ['orders'], ['shop_window_metrics'], 'Compare cancelled orders / all orders in equivalent post-action order cohorts.'],
    return_spike: ['Return-rate increase', ['returns','orders','settlements'], ['shop_window_metrics'], 'Compare distinct returned-order rates with the same observation lag.'],
    fee_spike: ['Abnormal fee-rate increase', ['settlements','orders','order_items'], ['order_economics','shop_window_metrics'], 'Compare weighted fees / sales for newly settled orders, accounting for fee schedules and SKU mix.'],
    payout_mismatch: ['Payout reconciliation shortfall', ['settlements','orders','order_items','products'], ['order_economics'], 'Reconcile a new statement or adjustment and check whether the order variance closes.'],
    low_stock: ['High-demand SKU with low stock', ['inventory','order_items','orders'], ['inventory_risk'], 'Collect a fresh stock snapshot after replenishment and recalculate coverage.'],
    shipment_risk: ['Open orders at risk of late dispatch', ['fulfillment','orders'], [], 'Collect dispatch confirmations and compare actual dispatch times with order deadlines.'],
    account_health: ['Active penalty-point warning', ['account_health'], [], 'Fetch new health records and verify an appeal, correction or expiry in the source.'],
  };
  const issueTypes = Object.keys(definitions);
  const raw = await query('SELECT * FROM raw.documents ORDER BY platform,shop_id,resource');
  for (const platform of platforms) await save(`raw/${platform}.json`, {
    note: 'Complete synthetic fixture batches, including all shops and supplements. Recorded API confidence levels still apply.',
    documents: raw.filter(row => row.platform === platform),
  });
  const core = {};
  for (const table of coreTables) core[`core.${table}`] = await query(`SELECT * FROM core.${table} ORDER BY 1,2`);
  const mart = {
    scope: 'Complete current fixture dataset. All aggregates and candidates use the full source population.',
    'mart.settings': await query('SELECT * FROM mart.settings'),
  };
  for (const view of martViews) {
    const rows = await query(`SELECT * FROM mart.${view} ORDER BY 1,2`);
    mart[`mart.${view}`] = view === 'agent_context' ? rows.map(row => row.context) : rows;
  }
  const contexts = mart['mart.agent_context'];
  const access = await exportAccess(db, root, output);
  assert.equal(core['core.orders'].length, 1344);
  assert.equal(core['core.order_items'].length, 1400);
  assert.equal(contexts.length, 29);
  assert.deepEqual([...new Set(contexts.map(row => row.issue_type))].sort(), [...issueTypes].sort());
  for (const platform of platforms) {
    const types = [...new Set(contexts.filter(row => row.shop_key === `${platform}:1001`).map(row => row.issue_type))].sort();
    assert.deepEqual(types, issueTypes.filter(type => type !== 'account_health' || platform !== 'shopify').sort());
  }
  assert.equal(contexts.filter(row => row.shop_key === 'shopee-open-platform:1002').length, 0);
  const columns = [];
  for (const [relation, rows] of [['raw.documents',raw], ...Object.entries(access), ...Object.entries(core), ...Object.entries(mart).filter(([name]) => name.startsWith('mart.'))]) {
    const [schema, table] = relation.split('.');
    const fields = (await query('SELECT column_name FROM information_schema.columns WHERE table_schema=$1 AND table_name=$2 ORDER BY ordinal_position', [schema,table])).map(row => row.column_name);
    assert.ok(rows.length, `No sample for ${relation}`);
    const exported = relation === 'mart.agent_context' ? rows.map(context => ({ shop_key: context.shop_key, issue_key: context.issue_key, context })) : rows;
    const missing = fields.filter(field => !exported.every(row => Object.hasOwn(row, field)));
    assert.deepEqual(missing, [], `Missing fields in ${relation}`);
    columns.push({ relation, rows: rows.length, fields, missing_fields: missing,
      export_shape: relation === 'mart.agent_context' ? 'JSON file exports context objects; SQL wrapper is shown in the README complete-record example.' : 'Full relational rows.' });
  }
  const supplement = platform => raw.find(doc => doc.platform === platform && doc.shop_id === '1001' && doc.resource === 'supplement').payload;
  const nativeOrder = (platform, id) => {
    const p = raw.find(doc => doc.platform === platform && doc.shop_id === '1001' && doc.resource === 'orders').payload;
    if (platform === 'shopee-open-platform') return p.response.order_list.find(row => row.order_sn === id);
    if (platform === 'lazada') return p.data.orders.find(row => String(row.order_id) === id);
    return p.data.orders.nodes.find(row => baseId(row.id) === id);
  };
  const cases = [];
  for (const [type, [label, tables, views, verify]] of Object.entries(definitions)) {
    const examples = {};
    for (const platform of platforms) {
      const packet = contexts.find(row => row.issue_type === type && row.platform === platform);
      if (!packet) {
        assert.equal(type, 'account_health');
        assert.equal(platform, 'shopify');
        examples[platform] = { status: 'unsupported', reason: 'No health feed in the fixture; absence does not measure zero risk.' };
        continue;
      }
      const s = supplement(platform);
      const recent = value => Date.parse(value) >= Date.parse(packet.windows.recent_start);
      let id;
      let source;
      if (type === 'product_reviews') source = { reviews: s.reviews.filter(row => row.sku === packet.entity_key && row.rating <= 2 && recent(row.reviewed_at)).slice(0,3) };
      if (type === 'promotion_loss') {
        id = '100294';
        source = { order: nativeOrder(platform,id), enrichment: s.order_enrichment.find(row => row.order_id === id), product: s.products.find(row => row.sku === 'SHIRT-M'), promotion: s.promotions[0], settlement: s.settlements.find(row => row.order_id === id) };
      }
      if (type === 'cancellation_spike') {
        id = baseId(core['core.orders'].find(row => row.shop_key === packet.shop_key && row.status === 'cancelled' && recent(row.ordered_at)).order_id);
        source = { order: nativeOrder(platform,id) };
      }
      if (type === 'return_spike') {
        const returned = s.returns.find(row => recent(row.requested_at));
        id = returned.order_id;
        source = { return: returned, order: nativeOrder(platform,id), settlement: s.settlements.find(row => row.order_id === id) };
      }
      if (type === 'fee_spike') source = { baseline_order: nativeOrder(platform,'100000'), baseline_settlement: s.settlements.find(row => row.order_id === '100000'), recent_order: nativeOrder(platform,'100294'), recent_settlement: s.settlements.find(row => row.order_id === '100294') };
      if (type === 'payout_mismatch') {
        id = baseId(packet.entity_key);
        source = { order: nativeOrder(platform,id), settlement: s.settlements.find(row => row.order_id === id) };
      }
      if (type === 'low_stock') {
        const end = Date.parse(packet.as_of);
        const demandOrder = core['core.orders'].find(order => order.shop_key === packet.shop_key && Date.parse(order.ordered_at) >= end-7*86400000 && Date.parse(order.ordered_at) < end && core['core.order_items'].some(line => line.shop_key === packet.shop_key && line.order_id === order.order_id && line.sku === packet.entity_key && ['open','shipped','completed'].includes(line.status)));
        source = { product: s.products.find(row => row.sku === packet.entity_key), stock_observations: s.inventory.filter(row => row.sku === packet.entity_key), demand_order: nativeOrder(platform,baseId(demandOrder.order_id)) };
      }
      if (type === 'shipment_risk') {
        id = baseId(packet.evidence[0].order_id);
        source = { order: nativeOrder(platform,id), fulfillment: s.fulfillment.find(row => row.order_id === id) };
      }
      if (type === 'account_health') source = { events: s.account_health };
      assert.ok(source && !Object.values(source).includes(undefined), `Missing raw sample: ${platform}/${type}`);
      const sourceOrderIds = new Set();
      const collectOrderIds = value => {
        if (Array.isArray(value)) { value.forEach(collectOrderIds); return; }
        if (!value || typeof value !== 'object') return;
        for (const [key,entry] of Object.entries(value)) {
          if (key === 'order_id' || key === 'order_sn' || (key === 'id' && String(entry).includes('/Order/'))) sourceOrderIds.add(baseId(entry));
          if (entry && typeof entry === 'object') collectOrderIds(entry);
        }
      };
      collectOrderIds(source);
      if (source.order || source.recent_order || source.demand_order) {
        source.order_enrichment = s.order_enrichment.filter(row => sourceOrderIds.has(baseId(row.order_id)));
        if (tables.includes('products') && !source.product) {
          const skus = new Set(core['core.order_items'].filter(row => row.shop_key === packet.shop_key && sourceOrderIds.has(baseId(row.order_id))).map(row => row.sku));
          source.products = s.products.filter(row => skus.has(row.sku));
        }
      }
      if (platform === 'lazada' && sourceOrderIds.size) {
        const items = raw.find(doc => doc.platform === platform && doc.shop_id === '1001' && doc.resource === 'order_items').payload;
        source.order_items = items.responses.flatMap(response => response.data).filter(row => sourceOrderIds.has(baseId(row.order_id)));
      }
      const coreSamples = {};
      for (const table of tables) {
        let rows = core[`core.${table}`].filter(row => row.shop_key === packet.shop_key);
        if (sourceOrderIds.size && rows.some(row => Object.hasOwn(row,'order_id'))) rows = rows.filter(row => sourceOrderIds.has(baseId(row.order_id)));
        else if (rows.some(row => Object.hasOwn(row,'sku')) && ['product_reviews','low_stock'].includes(type)) rows = rows.filter(row => row.sku === packet.entity_key);
        if (table === 'products' && source.product) rows = rows.filter(row => row.sku === source.product.sku);
        if (table === 'products' && source.products) rows = rows.filter(row => source.products.some(product => product.sku === row.sku));
        if (type === 'low_stock' && ['orders','order_items'].includes(table)) {
          const end = Date.parse(packet.as_of);
          const demandIds = new Set(core['core.order_items'].filter(line => line.shop_key === packet.shop_key && line.sku === packet.entity_key && ['open','shipped','completed'].includes(line.status)).map(line => line.order_id));
          rows = rows.filter(row => demandIds.has(row.order_id));
          if (table === 'orders') rows = rows.filter(row => Date.parse(row.ordered_at) >= end-7*86400000 && Date.parse(row.ordered_at) < end);
          else {
            const recentIds = new Set(core['core.orders'].filter(order => order.shop_key === packet.shop_key && Date.parse(order.ordered_at) >= end-7*86400000 && Date.parse(order.ordered_at) < end).map(order => order.order_id));
            rows = rows.filter(row => recentIds.has(row.order_id));
          }
        }
        if (table === 'reviews') rows = rows.filter(row => row.rating <= 2 && recent(row.reviewed_at));
        if (table === 'inventory') rows.sort((a,b) => Date.parse(b.observed_at)-Date.parse(a.observed_at));
        assert.ok(rows.length, `Missing core sample: ${type}/${table}`);
        coreSamples[`core.${table}`] = rows.slice(0,3);
      }
      examples[platform] = { source_note: 'Native order fields and/or explicitly labeled demo supplements, selected from full raw batches.', raw_samples: source, core_samples: coreSamples, mart_metrics: packet.metrics, agent_context: packet };
    }
    cases.push({ issue_type: type, label, core_tables: tables, mart_views: views, verification_input: verify, examples });
  }

  const edgeCases = [];
  const edge = async (name, mutation, inspect, validate) => {
    await db.exec('BEGIN');
    try {
      await db.exec(mutation);
      const rows = await query(inspect);
      validate(rows);
      edgeCases.push({ case: name, scope: 'Isolated core mutation, rolled back after sampling. Not a native API fixture or permanent change.', mutation_sql: mutation, inspection_sql: inspect, observed: rows });
    } finally { await db.exec('ROLLBACK'); }
  };
  const orderQuery = "SELECT shop_key,order_id,status,cogs,financials_complete,contribution_margin,payout_variance FROM mart.order_economics WHERE shop_key='lazada:1001' AND order_id='100000'";
  for (const status of ['mixed','unknown','shipped']) await edge(`${status}_order_state`, `UPDATE core.orders SET status='${status}' WHERE shop_key='lazada:1001' AND order_id='100000'`, orderQuery, rows => assert.equal(rows[0].financials_complete,status === 'shipped'));
  await edge('missing_product_cost', "UPDATE core.products SET unit_cost=NULL WHERE shop_key='lazada:1001' AND sku='SHIRT-M'", orderQuery, rows => assert.equal(rows[0].contribution_margin,null));
  await edge('missing_fee', "UPDATE core.settlements SET fee_amount=NULL WHERE shop_key='lazada:1001' AND order_id='100000'", orderQuery, rows => assert.equal(rows[0].contribution_margin,null));
  const stockQuery = "SELECT i.*, (SELECT count(*)::int FROM mart.issue_candidates c WHERE c.shop_key=i.shop_key AND c.issue_type='low_stock' AND c.entity_key=i.sku) AS stock_alerts FROM mart.inventory_risk i WHERE i.shop_key='lazada:1001' AND i.sku='SHIRT-M'";
  await edge('unknown_stock', "UPDATE core.inventory SET available=NULL WHERE shop_key='lazada:1001' AND sku='SHIRT-M'", stockQuery, rows => { assert.equal(rows[0].available,null); assert.equal(rows[0].stock_alerts,0); });
  await edge('out_of_stock', "UPDATE core.inventory SET available=0 WHERE shop_key='lazada:1001' AND sku='SHIRT-M'", stockQuery, rows => { assert.equal(Number(rows[0].days_of_cover),0); assert.equal(rows[0].stock_alerts,1); });
  await edge('stale_stock', "UPDATE mart.settings SET as_of=as_of+interval '2 days'", stockQuery, rows => assert.equal(rows[0].stock_alerts,0));
  await edge('no_observed_demand', "UPDATE core.order_items SET status='cancelled' WHERE shop_key='lazada:1001' AND sku='SHIRT-M'", stockQuery, rows => { assert.equal(rows[0].daily_units,null); assert.equal(rows[0].stock_alerts,0); });
  await edge('expired_penalty', "UPDATE core.account_health SET expires_at='2026-10-30T23:00:00+07:00' WHERE shop_key='lazada:1001'", "SELECT count(*)::int AS health_alerts FROM mart.issue_candidates WHERE shop_key='lazada:1001' AND issue_type='account_health'", rows => assert.equal(rows[0].health_alerts,0));
  await edge('insufficient_review_sample', "DELETE FROM core.reviews WHERE shop_key='lazada:1001' AND reviewed_at>='2026-10-29T00:00:00+07:00' AND review_id NOT IN (SELECT review_id FROM core.reviews WHERE shop_key='lazada:1001' AND sku='SHIRT-M' AND reviewed_at>='2026-10-29T00:00:00+07:00' ORDER BY review_id LIMIT 2)", "SELECT count(*)::int AS review_alerts FROM mart.issue_candidates WHERE shop_key='lazada:1001' AND issue_type='product_reviews'", rows => assert.equal(rows[0].review_alerts,0));
  assert.equal(Number((await query('SELECT count(*) FROM mart.issue_candidates'))[0].count),29);

  const dictionary = await read('DATA-DICTIONARY.md');
  const samples = sampleTables(dictionary);
  const future = {};
  for (const group of samples.filter(group => group.markdown.includes('Illustrative example'))) {
    for (const line of group.markdown.split('\n').slice(2)) {
      const cells = line.split('|').slice(1,-1).map(cell => cell.trim());
      future[cells[0].replaceAll('`','')] = JSON.parse(cells.at(-1).slice(1,-1).replaceAll('&#124;','|').replaceAll('&#96;','`'));
    }
  }
  assert.equal(Object.keys(future).length,6);
  const coverage = {
    scope: 'All current dictionary sample rows and exported database fields, nine implemented issue types, healthy control, unsupported Shopify health, and the isolated edge cases listed here. No claim about every possible production input.',
    dictionary_sample_tables: samples.length,
    dictionary_sample_rows: samples.reduce((count,group) => count+group.rows,0),
    dictionary_examples_copied_verbatim: true,
    raw_documents: raw.length, core_tables: coreTables.length, mart_views: martViews.length,
    access_tables: 3, access_views: 1, user_shop_grants: access['access.user_shop_access'].length,
    column_coverage: columns,
    issue_types: issueTypes.map(type => ({ issue_type: type, candidates: contexts.filter(row => row.issue_type === type).length, platforms: [...new Set(contexts.filter(row => row.issue_type === type).map(row => row.platform))] })),
    healthy_control: { shop_key: 'shopee-open-platform:1002', candidates: 0 },
    unsupported_data: { shop_key: 'shopify:1001', capability: 'account_health', value: 'unsupported', candidates: 0 },
    edge_cases: edgeCases.map(row => ({ case: row.case, passed: true })),
    illustrative_future_tables: Object.keys(future),
  };
  await save('core.json',core);
  await save('mart.json',mart);
  await save('cases.json',cases);
  await save('edge-cases.json',edgeCases);
  await save('future-agent-examples.json',{ status: 'Illustrative dictionary examples only; these tables and operations are not implemented.', tables: future });
  await save('metadata.json',{ manifest: JSON.parse(await read('manifest.json')), validation_report: JSON.parse(await read('mart/validation-report.json')) });
  await save('coverage.json',coverage);

  const marker = '<!-- BEGIN GENERATED COMPLETE SAMPLES -->';
  let appendix = `\n${marker}\n\n## 7. Complete dictionary samples and case coverage\n\n`;
  appendix += `This generated section includes **all ${coverage.dictionary_sample_rows} sample rows from ${samples.length} dictionary tables**, all 11 core tables, all eight mart views, all nine business issue types and ${edgeCases.length} isolated edge cases. Rebuild with \`npm.cmd run example\`.\n\n`;
  appendix += 'The raw files contain all nine fixture batches across four shops. [core.json](core.json) and [mart.json](mart.json) contain the complete dataset. [access.json](access.json) contains users, merchants, memberships and per-user shop results; use the [access guide](../../access/README.md) before exposing data to a user. [cases.json](cases.json) traces each business case from platform records through core records to its agent packet. [coverage.json](coverage.json) records the field and case checks.\n\n';
  appendix += '### 7.1 Every implemented business case\n\n| Case | Core inputs | Mart calculations | Platform coverage |\n|---|---|---|---|\n';
  for (const item of cases) {
    const coreLabels = item.core_tables.map(table => '`core.'+table+'`').join(', ');
    const martLabels = item.mart_views.map(view => '`mart.'+view+'`').join(', ') || 'Direct candidate rule';
    appendix += `| ${item.label} | ${coreLabels} | ${martLabels} | ${item.issue_type === 'account_health' ? 'Shopee, Lazada; Shopify unsupported' : 'Shopee, Lazada, Shopify'} |\n`;
  }
  appendix += '\nThe review case groups the negative spike and repeated sizing complaints. Each case below includes a full Shopee packet; the JSON export includes each supported platform.\n\n';
  for (const item of cases) appendix += `#### ${item.issue_type}: ${item.label}\n\nSource, core and mart samples for every platform are in \`cases.json\` under this issue type. Verification input: ${item.verification_input}\n\n${fence(item.examples['shopee-open-platform'].agent_context)}\n\n`;
  appendix += '### 7.2 Healthy control and unsupported data\n\n'+fence({ healthy_control: coverage.healthy_control, unsupported_data: coverage.unsupported_data })+'\n\n';
  appendix += '### 7.3 Missing-data and boundary cases\n\nThese samples use isolated SQL mutations rolled back after inspection. Full mutation/query/result triples are in [edge-cases.json](edge-cases.json). They do not alter the fixture.\n\n';
  for (const item of edgeCases) appendix += `#### ${item.case}\n\n${fence(item.observed)}\n\n`;
  appendix += 'Source-adapter handling for Lazada mixed unit statuses and an unknown Shopee status is additionally checked by `tests/test_connectors.py`. Full exports also include baseline/recent periods, open/cancelled orders, refunds, previous/current stock, shop-scoped ID collisions, separate seller/platform funding, null optional fields and both issue severities.\n\n';
  appendix += '### 7.4 Every dictionary sample column, included here\n\nThese tables are copied verbatim from [DATA-DICTIONARY.md](../../DATA-DICTIONARY.md): raw fields, core columns, mart metrics, evidence shapes, capabilities, metadata and proposed downstream records. Nested JSON excerpts retain the shortening used in that dictionary. Proposed `agent.*` records are illustrative; they are not implemented tables or completed actions.\n\n';
  for (const group of samples) appendix += `#### ${group.section}\n\n${group.markdown}\n\n`;
  appendix += '### 7.5 Complete record examples for every shared table and view\n\nThese objects show all columns together, including inherited order fields and SQL wrapper columns. The JSON files contain all remaining records.\n\n';
  for (const [relation,rows] of Object.entries(access)) appendix += `#### ${relation}\n\n${fence(rows[0])}\n\n`;
  for (const [relation,rows] of Object.entries(core)) appendix += `#### ${relation}\n\n${fence(rows[0])}\n\n`;
  appendix += `#### mart.settings\n\n${fence(mart['mart.settings'][0])}\n\n`;
  for (const view of martViews) {
    const relation = `mart.${view}`;
    const record = view === 'agent_context' ? { shop_key: contexts[0].shop_key, issue_key: contexts[0].issue_key, context: contexts[0] } : mart[relation][0];
    appendix += `#### ${relation}\n\n${fence(record)}\n\n`;
  }
  appendix += '<!-- END GENERATED COMPLETE SAMPLES -->\n';
  await writeFile(new URL('reference.md',output), '# Complete dictionary samples and record reference\n\nStart with the [use-case guide](README.md) for step-by-step explanations. This reference preserves every dictionary example and complete record sample.\n'+appendix);
  await writeUseCaseGuides({ db, output, raw, core, mart, cases, coverage });
  console.log(`Complete coverage: ${raw.length} raw documents, ${coreTables.length} core tables, ${martViews.length} mart views, ${contexts.length} packets, ${issueTypes.length} issue types, ${edgeCases.length} edge cases, ${coverage.dictionary_sample_rows} dictionary sample rows. All checks passed.`);
}
