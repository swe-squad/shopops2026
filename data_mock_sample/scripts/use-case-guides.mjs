import { mkdir, writeFile } from 'node:fs/promises';
import assert from 'node:assert/strict';

// Each guide explains a seller question with the same six-step structure.
const playbooks = {
  product_reviews: {
    question: 'Why are buyers suddenly complaining that this shirt is too small?',
    marts: ['product_review_metrics','issue_candidates','agent_context'],
    calculation: 'Negative-review rate = one/two-star reviews / all reviews. The recent shirt cohort has 11 / 11 = 100%; baseline has 3 / 96 = 3.125%. All 11 recent negatives contain sizing keywords. These measurements support one product issue with two triggers.',
    trigger: 'At least 5 recent and 10 baseline reviews; at least 3 recent negatives; recent negative rate ≥ max(20%, twice baseline). Three sizing mentions add the repeated-sizing trigger.',
    query: "SELECT shop_key,sku,period,reviews,negative_reviews,negative_rate,sizing_mentions FROM mart.product_review_metrics WHERE shop_key='shopee-open-platform:1001' AND sku='SHIRT-M' ORDER BY period;",
    options: [
      ['Inspect stock measurements and correct the size guide if wrong','Reduce expectation mismatch; requires staff measurement and current chart','Low direct cost; benefit needs later evidence','Listing text/chart edits may be reverted if the original state is saved'],
      ['Add a seller-approved fit warning','Help buyers choose a size; requires current listing content','Could reduce conversion; impact is unknown','Listing text can be restored from the saved before-state'],
    ],
    verify: 'Collect new reviews for orders placed after the listing change, allow review delay, and compare negative sizing-review rates with an explicit minimum sample. Example success criterion: below 10% after 20 eligible reviews. This criterion is illustrative; no successful outcome is pre-generated.',
    limitations: 'Keyword matches suggest a sizing problem; the current data does not include the actual size chart or prove a manufacturing defect.',
  },
  promotion_loss: {
    question: 'Is the SAVE90 offer associated with orders that lose money?',
    marts: ['order_economics','promotion_performance','issue_candidates','agent_context'],
    calculation: 'For order 100294: 200,000 sales − 90,000 seller discount − 30,000 fees − 8,000 shipping − 0 refund = 72,000 expected payout. Subtract 130,000 product cost: margin = −58,000 VND. Across the recent offer cohort, 11 of 16 linked orders have complete finances; all 11 lose money, totaling −1,368,000 VND in this Shopee shop.',
    trigger: 'At least 3 negative-margin linked orders and a negative sum of known contribution margins.',
    query: "SELECT order_id,gross_sales,seller_discount,fee_amount,seller_shipping_cost,refund_amount,cogs,expected_payout,contribution_margin,financials_complete FROM mart.order_economics WHERE shop_key='shopee-open-platform:1001' AND order_id='100294';",
    secondQuery: "SELECT shop_key,promotion_id,orders,finance_complete_orders,loss_orders,contribution_margin FROM mart.promotion_performance WHERE shop_key='shopee-open-platform:1001' AND promotion_id='SAVE90';",
    options: [
      ['Pause the offer after checking current rules','Stop new exposure while investigating; requires live voucher ID and enabled state','Sales may fall; already placed orders are unaffected by the proposed pause','Re-enable only if the platform supports it and previous rules were saved'],
      ['Reduce the seller-funded discount for future orders','Improve projected margin; requires current discount rules and expected fees','Conversion may fall; refunds and fees can still create losses','Restore earlier rules if the API permits the change'],
    ],
    verify: 'Collect newly settled orders after the approved change. Compare margin per eligible order, total margin and sales volume with comparable product mix. Example target: nonnegative contribution margin on at least 20 finance-complete new orders.',
    limitations: 'The example changes both discount and fee rate. Association does not prove the voucher alone caused the loss. Margin excludes advertising, overhead and tax; unknown financials are not zero.',
  },
  cancellation_spike: {
    question: 'Are unusually many newly placed orders being cancelled?',
    marts: ['shop_window_metrics','issue_candidates','agent_context'],
    calculation: 'Recent: 12 cancelled orders / 48 orders = 25%. Baseline: 12 / 288 = 4.1667%. The recent rate is six times the baseline. Count orders once, regardless of how many item rows they contain.',
    trigger: 'At least 10 recent and 20 baseline orders, at least 3 recent cancellations, and recent rate ≥ max(10%, twice baseline).',
    query: "SELECT shop_key,period,orders,cancelled_orders,cancellation_rate FROM mart.shop_window_metrics WHERE shop_key='shopee-open-platform:1001' ORDER BY period;",
    options: [
      ['Review recent cancelled orders and collect cancellation reasons','Identify whether stock, fulfillment or buyer choice drives cancellations','Staff review time; current fixtures do not include cancellation reason codes','Read-only investigation requires no rollback'],
      ['Reconcile availability for affected SKUs before changing listings','Reduce avoidable cancellations if stock mismatch is confirmed','Requires new stock evidence; unnecessary listing changes may reduce sales','Listing availability can be restored if supported'],
    ],
    verify: 'Measure cancelled / all orders in a new post-action cohort. Example target: below 10% over at least 50 new orders, with a comparable cancellation observation delay.',
    limitations: 'The data proves a rate change, but does not establish why orders were cancelled. Do not infer stock problems from cancellation counts alone.',
  },
  return_spike: {
    question: 'Are more fulfilled purchases leading to return requests?',
    marts: ['shop_window_metrics','issue_candidates','agent_context'],
    calculation: 'Recent cohort: 10 distinct returned orders / 32 shipped/completed orders = 31.25%. Baseline: 1 / 276 ≈ 0.3623%. A case contributes once per order; its refund amount is already included in settlement financials.',
    trigger: 'At least 10 recent and 20 baseline fulfilled orders, at least 3 returned recent-cohort orders, and recent rate ≥ max(10%, twice baseline).',
    query: "SELECT shop_key,period,fulfilled_orders,returned_orders,return_rate FROM mart.shop_window_metrics WHERE shop_key='shopee-open-platform:1001' ORDER BY period;",
    options: [
      ['Review return reasons and inspect affected items','Find whether fit, quality or another issue needs action','Staff inspection cost; current cases are order-level and do not identify returned unit quantities','Investigation requires no rollback'],
      ['Correct confirmed listing or packing issues','Reduce recurrence after evidence confirms a cause','Needs additional listing/packing evidence; changes may have a sales cost','Save prior listing configuration before an editable change'],
    ],
    verify: 'Compare distinct returned-order rates in post-action cohorts with the same number of days since purchase. Define minimum sample size and observation lag before judging the outcome.',
    limitations: 'Recent cohorts have had less time to generate returns. The detector counts observed return requests, not only refunded cases. Shipped/completed is the denominator, not a guaranteed delivered-order count.',
  },
  fee_spike: {
    question: 'Did the effective platform fee rate change unexpectedly?',
    marts: ['order_economics','shop_window_metrics','issue_candidates','agent_context'],
    calculation: 'Baseline order 100000: 20,000 fees / 400,000 sales = 5%. Recent order 100294: 30,000 / 200,000 = 15%. The whole-window weighted rates are also 5% and 15%: an increase of 10 percentage points.',
    trigger: 'At least 10 recent and 20 baseline finance-complete orders and a fee-rate increase greater than 3 percentage points.',
    query: "SELECT shop_key,period,settled_orders,effective_fee_rate FROM mart.shop_window_metrics WHERE shop_key='shopee-open-platform:1001' ORDER BY period;",
    options: [
      ['Reconcile source statements and current fee schedules','Determine whether the change is expected, erroneous, or caused by product mix','Staff time; aggregate fee data has no fee-category breakdown','Read-only investigation requires no rollback'],
      ['Model pricing or campaign changes after reconciliation','Recover margin if a valid recurring fee increase is confirmed','May reduce conversion; requires current prices and campaign terms','Price edits can be restored where the connector supports it'],
    ],
    verify: 'Collect new finance-complete settlements, calculate sum(fees) / sum(gross sales), and compare with the confirmed expected schedule and product mix. Do not assume returning to 5% is possible.',
    limitations: 'An effective rate is an observed aggregate, not an official fee schedule. The fixture has only total fees, so a fee-category explanation requires a new source.',
  },
  payout_mismatch: {
    question: 'Did this order pay out less than the modeled settlement predicts?',
    marts: ['order_economics','issue_candidates','agent_context'],
    calculation: 'This order has 250,000 sales − 10,000 seller discount − 37,500 fees − 8,000 shipping − 0 refunds = 194,500 VND expected payout. Actual payout is 169,500 VND. Variance = actual − expected = −25,000 VND.',
    trigger: 'Absolute payout variance exceeds 1,000 VND and the settlement falls in the recent window.',
    query: "SELECT shop_key,order_id,gross_sales,seller_discount,fee_amount,seller_shipping_cost,refund_amount,expected_payout,actual_payout,payout_variance FROM mart.order_economics WHERE shop_key='shopee-open-platform:1001' AND order_id='100296';",
    options: [
      ['Fetch detailed adjustments and fee lines for this order','Check whether an omitted legitimate adjustment explains the shortfall','Staff/API cost; the current fixture does not provide adjustment details','Read-only investigation requires no rollback'],
      ['Prepare a reconciliation case for seller review','Give the seller a traceable order-level evidence bundle','Outcome and recovery are unknown; submitting a case is a separate approved action','An external submission may not be reversible'],
    ],
    verify: 'Fetch a new source statement or adjustment. Recompute expected and actual payout and check whether the discrepancy is explained or corrected. Preserve the original evidence for comparison.',
    limitations: 'The discrepancy is against this simplified model. Missing taxes, adjustments or shipping pass-throughs can explain differences in live data; it does not prove the platform underpaid.',
  },
  low_stock: {
    question: 'Will the popular shirt sell out before the seller replenishes it?',
    marts: ['inventory_risk','issue_candidates','agent_context'],
    calculation: 'The latest sellable stock is 2 shirts. Recognized noncancelled demand is 64 units over 7 days: 64 / 7 ≈ 9.1429 per day. Coverage = 2 / (64 / 7) = 0.21875 days, about 5.25 hours under this simple average-demand assumption.',
    trigger: 'Coverage below 2 days, average demand at least 1 unit/day, and selected stock observations no more than 24 hours old.',
    query: "SELECT shop_key,sku,available,oldest_location_observation,daily_units,days_of_cover FROM mart.inventory_risk WHERE shop_key='shopee-open-platform:1001' AND sku='SHIRT-M';",
    options: [
      ['Confirm stock and request supplier lead time/quote','Validate urgency and estimate a replenishment quantity','Staff time; unit cost is known but lead time and delivered purchase cost are missing','Investigation can be stopped; a purchase commitment may not be reversible'],
      ['After approval, arrange replenishment or adjust availability','Reduce stockout exposure or prevent overselling','Purchase cash requirement or lower sales; requires confirmed physical stock','Availability edits may be reverted; purchasing needs a separate rollback policy'],
    ],
    verify: 'Read a fresh post-replenishment stock snapshot. Recalculate days of cover with current demand. Example criterion: at least 2 days of cover, with all location snapshots less than 24 hours old.',
    limitations: 'Coverage is a trailing average, not a forecast. Do not simply increase marketplace stock without physical inventory. Unknown or stale stock suppresses the alert rather than becoming zero.',
  },
  shipment_risk: {
    question: 'Which open orders need dispatch attention now?',
    marts: ['issue_candidates','agent_context'],
    calculation: 'Select open orders with no dispatch timestamp and ship_by before as_of + 6 hours. The fixture has 4 qualifying orders; all 4 are already overdue at the frozen clock. Group them into one shop-level issue.',
    trigger: 'At least one open, unshipped order due before the next six-hour boundary. Cancelled orders are excluded.',
    query: "SELECT o.shop_key,o.order_id,o.status,f.ship_by,f.shipped_at,f.deadline_basis FROM core.orders o JOIN core.fulfillment f USING(shop_key,order_id) CROSS JOIN mart.settings s WHERE o.shop_key='shopee-open-platform:1001' AND o.status='open' AND f.shipped_at IS NULL AND f.ship_by<s.as_of+interval '6 hours' ORDER BY o.order_id;",
    options: [
      ['Prioritize packing and confirm carrier handoff availability','Focus staff on the four at-risk orders','Staff/overtime cost unknown; requires actual packing/carrier state','A work assignment can be changed; physical handoff cannot be undone'],
      ['After seller choice, arrange a supported pickup or handoff','Complete dispatch and limit further delay','Carrier availability and fees are unknown until checked','Pickup cancellation depends on the carrier/API'],
    ],
    verify: 'Collect genuine dispatch confirmations. Check shipped_at against each original deadline and confirm the open-risk backlog is cleared. Already late orders remain historically late even after dispatch.',
    limitations: 'These are demo dispatch deadlines, not official Shopee SLAs. This case reads core fulfillment directly; no dedicated shipping mart view exists.',
  },
  account_health: {
    question: 'Does the seller have active penalty events that need attention?',
    marts: ['issue_candidates','agent_context'],
    calculation: 'Keep events that occurred before as_of and expire after it. Sum incremental penalty_points, not repeated cumulative balances. The active demo event contributes 3 points.',
    trigger: 'At least 3 active demo penalty points.',
    query: "SELECT shop_key,event_id,occurred_at,expires_at,penalty_points,reason FROM core.account_health CROSS JOIN mart.settings s WHERE shop_key='shopee-open-platform:1001' AND occurred_at<s.as_of AND expires_at>s.as_of ORDER BY event_id;",
    options: [
      ['Review the source penalty and its supporting orders','Check whether the event is understood or disputable','Staff time; official policy and order-level penalty evidence must be fetched','Read-only review requires no rollback'],
      ['Prepare an appeal or operational correction for seller review','Address an eligible error or reduce recurrence','Appeal eligibility and success are unknown','An appeal submission may be irreversible'],
    ],
    verify: 'Fetch a new account-health observation or event history and confirm source-backed correction, appeal outcome or expiry. Keep expiry separate from evidence that an action caused improvement.',
    limitations: 'The threshold and events are synthetic, and Lazada health is a demo supplement. Shopify is explicitly unsupported. No official suspension threshold is inferred. This case reads core events directly.',
  },
};

const pick = (row, fields) => Object.fromEntries(fields.filter(key => Object.hasOwn(row,key)).map(key => [key,row[key]]));
const coreFields = {
  orders: ['shop_key','order_id','ordered_at','status','seller_discount','platform_discount','promotion_id'],
  order_items: ['shop_key','order_id','line_id','sku','quantity','unit_price','status'],
  products: ['shop_key','sku','unit_cost','cost_basis'],
  promotions: ['shop_key','promotion_id','funding','starts_at','ends_at'],
  settlements: ['shop_key','order_id','fee_amount','seller_shipping_cost','refund_amount','actual_payout','paid_at'],
  reviews: ['shop_key','review_id','order_id','sku','reviewed_at','rating','body'],
  returns: ['shop_key','return_id','order_id','requested_at','reason','status','refund_amount'],
  inventory: ['shop_key','sku','location_id','observed_at','available'],
  fulfillment: ['shop_key','order_id','ship_by','shipped_at','deadline_basis'],
  account_health: ['shop_key','event_id','occurred_at','expires_at','penalty_points','reason'],
};

export async function writeUseCaseGuides({ db, output, raw, core, mart, cases, coverage }) {
  const directory = new URL('use-cases/',output);
  await mkdir(directory,{ recursive: true });
  const json = value => '```json\n'+JSON.stringify(value,null,2)+'\n```';
  const query = async sql => (await db.query(sql)).rows;
  const sqlBlock = sql => '```sql\n'+sql.replaceAll(' FROM ','\nFROM ').replaceAll(' WHERE ','\nWHERE ').replaceAll(' AND ','\n  AND ').replaceAll(' ORDER BY ','\nORDER BY ')+'\n```';
  const baseId = value => String(value).split('/').at(-1);
  const files = [];
  const coveredMarts = new Set();

  for (const item of cases) {
    const spec = playbooks[item.issue_type];
    assert.ok(spec,`Missing use-case guide for ${item.issue_type}`);
    const example = item.examples['shopee-open-platform'];
    const packet = example.agent_context;
    const results = await query(spec.query);
    assert.ok(results.length,`No actual SQL result for ${item.issue_type}`);
    const second = spec.secondQuery ? await query(spec.secondQuery) : null;
    const relevant = {};
    for (const [relation,rows] of Object.entries(example.core_samples)) relevant[relation] = rows.slice(0, item.issue_type === 'product_reviews' ? 3 : 2).map(row => pick(row,coreFields[relation.split('.')[1]]));

    let page = `# ${spec.question}\n\n[Back to use-case index](../README.md) · [Complete field reference](../reference.md)\n\n`;
    page += `Use this case to answer: **${spec.question}**\n\n`;
    page += `Marts used: ${spec.marts.map(name => '`mart.'+name+'`').join(', ')}. The main calculation is shown below; \`issue_candidates\` applies the trigger and \`agent_context\` packages it for the planner.\n\n`;
    page += 'All measured values below come from the fixed fixture clock, **2026-10-31 00:00 Vietnam time**. Recent window is October 29–30; baseline is October 17–28. The raw/core snippets are representative records; the SQL aggregates use the full source population.\n\n';
    page += '## 1. Source data: what the connector received\n\nThe main example uses Shopee shop `1001`. Native order fields are provisional; operational records such as reviews, finance, inventory and health are explicitly labeled demo supplements.\n\n';
    page += json(example.raw_samples)+'\n\n';
    page += '<details>\n<summary>Compare the raw samples from Lazada and Shopify</summary>\n\n';
    for (const platform of ['lazada','shopify']) {
      const other = item.examples[platform];
      page += `### ${platform}\n\n`;
      page += other.status === 'unsupported' ? other.reason+'\n\n' : json(other.raw_samples)+'\n\n';
    }
    page += '</details>\n\n';
    page += '## 2. General core: the normalized business records\n\nThe adapters add `shop_key`, retain source IDs, standardize names/statuses, parse timestamps and convert money to exact decimal values. Use shop + entity ID when joining. The following excerpts contain only fields relevant to this case; full rows retain source-document pointers.\n\n';
    page += json(relevant)+'\n\n';
    page += '## 3. Mart: calculate the measurement\n\n'+spec.calculation+'\n\n';
    page += 'Run this query against the loaded PostgreSQL database:\n\n'+sqlBlock(spec.query)+'\n\n';
    page += 'Actual query result:\n\n'+json(results)+'\n\n';
    if (second) page += 'The order-level example then rolls up to the offer-level mart:\n\n'+sqlBlock(spec.secondQuery)+'\n\n'+json(second)+'\n\n';
    page += '## 4. Detection and the input passed to the agent\n\nTrigger: '+spec.trigger+'\n\n';
    page += 'Selected fields from the actual `mart.agent_context` packet:\n\n'+json(pick(packet,['issue_key','shop_key','platform','as_of','issue_type','entity_key','severity','metrics','decision_mode']))+'\n\n';
    page += 'The complete packet, including windows and evidence, is available in `cases.json` and `mart.json`. The planner uses these facts to classify the problem and request missing information.\n\n';
    page += '## 5. Plan → seller chooses → execute\n\nThe following are illustrative planning options. The data pipeline has not executed them. Current settings, target IDs, seller approval and connector results must be supplied by the next component.\n\n';
    page += '| Option | Expected purpose / required input | Cost and risk | Reversibility |\n|---|---|---|---|\n';
    for (const option of spec.options) page += '| '+option.join(' | ')+' |\n';
    page += '\nAfter the seller chooses an option in Telegram, store the approval under this packet’s `issue_key`, fetch the latest target state, execute idempotently, and retain before/after state and rollback parameters where supported. No numeric impact or success is invented here.\n\n';
    page += '## 6. Verify with new data\n\n'+spec.verify+'\n\n';
    page += '**What to collect next:** '+item.verification_input+'\n\nThe frozen fixture contains no post-action success data. Re-querying it proves reproducibility, not action effectiveness.\n\n';
    page += '**Interpretation limits:** '+spec.limitations+'\n\n';
    page += 'Full source → core → mart samples for each platform: [`cases.json`](../cases.json), find `issue_type = "'+item.issue_type+'"`. Boundary behavior and unsupported data are explained in the [controls guide](controls.md).\n';
    const filename = `${item.issue_type}.md`;
    await writeFile(new URL(filename,directory),page);
    files.push({ use_case: item.issue_type, file: 'use-cases/'+filename, marts: spec.marts, sql_queries_checked: second ? 2 : 1, stages: ['raw','core','mart','agent_input','seller_action_example','verification_inputs'] });
    for (const name of spec.marts) coveredMarts.add(name);
  }

  // shop_daily is a reporting use case, not a ninth detector pretending to be a tenth alert.
  const dailySql = "SELECT shop_key,business_date::text,currency,orders,cancelled_orders,unmapped_or_mixed_orders,finance_complete_orders,contribution_margin,fulfilled_gross_sales FROM mart.shop_daily WHERE business_date='2026-10-30' ORDER BY shop_key;";
  const dailyRows = await query(dailySql);
  assert.equal(dailyRows.length,4);
  const shop = 'shopee-open-platform:1001';
  const dayOrders = core['core.orders'].filter(row => row.shop_key === shop && Date.parse(row.ordered_at)>=Date.parse('2026-10-30T00:00:00+07:00'));
  const selectedOrders = [dayOrders.find(row => row.status === 'completed'),dayOrders.find(row => row.status === 'cancelled')];
  const ids = new Set(selectedOrders.map(row => row.order_id));
  const sourceOrders = raw.find(row => row.platform === 'shopee-open-platform' && row.shop_id === '1001' && row.resource === 'orders').payload.response.order_list.filter(row => ids.has(row.order_sn));
  const dailySupplement = raw.find(row => row.platform === 'shopee-open-platform' && row.shop_id === '1001' && row.resource === 'supplement').payload;
  const sourceDaily = {
    native_orders: sourceOrders,
    demo_supplement: {
      products: dailySupplement.products.filter(row => row.sku === 'SHIRT-M'),
      order_enrichment: dailySupplement.order_enrichment.filter(row => ids.has(row.order_id)),
      settlements: dailySupplement.settlements.filter(row => ids.has(row.order_id)),
    },
  };
  const dailyCore = {
    'core.products': core['core.products'].filter(row => row.shop_key === shop && row.sku === 'SHIRT-M').map(row => pick(row,coreFields.products)),
    'core.orders': selectedOrders.map(row => pick(row,coreFields.orders)),
    'core.order_items': core['core.order_items'].filter(row => row.shop_key === shop && ids.has(row.order_id)).map(row => pick(row,coreFields.order_items)),
    'core.settlements': core['core.settlements'].filter(row => row.shop_key === shop && ids.has(row.order_id)).map(row => pick(row,coreFields.settlements)),
  };
  let daily = '# How did each shop perform today?\n\n[Back to index](../README.md)\n\nUse `mart.shop_daily` to build a daily seller digest or agency dashboard. This is a reporting use case and does not automatically create an issue.\n\n';
  daily += '## 1. Source data\n\nTwo actual Shopee order excerpts for October 30 show a completed purchase and a cancellation. The explicit supplement adds costs, order discounts and settlement data. Full-day totals below include all 24 orders, not only these two examples.\n\n'+json(sourceDaily)+'\n\n';
  daily += '## 2. General core\n\n'+json(dailyCore)+'\n\nProduct unit costs are joined by shop + SKU when calculating `mart.order_economics`. A cancelled order has no settled margin here. The daily view groups those per-order facts by shop, local order date and currency.\n\n';
  daily += '## 3. Mart query and actual result\n\n'+sqlBlock(dailySql)+'\n\n'+json(dailyRows)+'\n\n';
  daily += 'For the affected Shopee shop, October 30 has 24 orders, 6 cancellations, 14 finance-complete orders and −622,000 VND summed known contribution margin. Four orders are still open. `contribution_margin` covers eligible orders only; `fulfilled_gross_sales` is before the separately recorded order discounts. The date is the local order date, not the payout date.\n\n';
  daily += '## 4. Input to the next component\n\nPass the four daily rows to a reporting agent as `daily_shop_summary`, together with `as_of`, currency and completeness counts. This is an illustrative report envelope, not a stored `mart.agent_context` issue packet:\n\n';
  daily += json({ report_type: 'daily_shop_summary', as_of: mart['mart.settings'][0].as_of, business_date: '2026-10-30', rows: dailyRows })+'\n\n';
  daily += '## 5. Seller use\n\nThe seller can open the voucher-loss case to investigate margin or the cancellation case to inspect operational changes. Do not infer that all 24 orders were measured for profit or that a low daily total proves one specific cause.\n\n';
  daily += '## 6. Verify later\n\nCollect new orders and settlements, rebuild the daily view and compare equivalent local days with finance completeness shown. A changing subtotal can reflect later settlement availability. There is no seller-approved action or observed improvement in this reporting example.\n';
  await writeFile(new URL('daily_summary.md',directory),daily);
  files.push({ use_case: 'daily_summary', file: 'use-cases/daily_summary.md', marts: ['shop_daily','order_economics'], sql_queries_checked: 1, stages: ['raw','core','mart','report_input','seller_use','verification_inputs'] });
  coveredMarts.add('shop_daily');

  const control = '# Healthy shops, missing data and boundary behavior\n\n[Back to index](../README.md)\n\n'+
    'Use these controls to interpret an empty issue list correctly.\n\n'+
    '## Healthy control\n\nRaw Shopee shop `1002` is normalized through the same adapters and marts. It has normal baseline/recent measurements and no candidates. Its orders and metrics remain visible in `core.json` and `mart.json`.\n\n'+json(coverage.healthy_control)+'\n\n'+
    '## Unsupported data\n\nShopify has no account-health feed in this fixture. An empty health issue list does not demonstrate zero penalty points. Check `core.shops.capabilities` before interpreting missing measurements.\n\n'+json(coverage.unsupported_data)+'\n\n'+
    '## Missing and boundary inputs\n\nThe [edge-case samples](../edge-cases.json) show isolated input changes, the SQL used to inspect them and their observed outputs. Each mutation is rolled back.\n\n'+
    '| Input condition | Expected behavior |\n|---|---|\n'+
    '| Missing product cost or fees | Margin stays unknown; no zero-cost assumption. |\n'+
    '| Mixed or unknown order state | Settled-margin eligibility is suppressed pending explicit interpretation. |\n'+
    '| Recognized shipped order with complete settlement | Eligible for financial calculations; does not assert delivery. |\n'+
    '| Unknown stock | Coverage is unknown; no low-stock claim. |\n'+
    '| Known zero stock with demand | Coverage is zero and a stock candidate is emitted. |\n'+
    '| Stale stock | Stock candidate is suppressed until a fresh snapshot is collected. |\n'+
    '| No observed recognized demand | Coverage is unknown; do not divide by zero or invent a forecast. |\n'+
    '| Expired penalty | Event no longer contributes to active-point candidates. |\n'+
    '| Insufficient review sample | Comparison rule waits for enough evidence. |\n\n'+
    'No candidate can mean healthy, unsupported, unknown, stale or insufficient data. The planner must inspect capabilities, completeness, observation time and sample size before explaining the result to the seller.\n';
  await writeFile(new URL('controls.md',directory),control);
  assert.deepEqual([...coveredMarts].sort(), ['order_economics','shop_daily','shop_window_metrics','product_review_metrics','inventory_risk','promotion_performance','issue_candidates','agent_context'].sort());
  coverage.use_case_guides = { guides: files, controls: 'use-cases/controls.md', covered_marts: [...coveredMarts].sort(), all_marts_covered: true, all_issue_types_covered: cases.every(item => files.some(file => file.use_case === item.issue_type)) };
  await writeFile(new URL('coverage.json',output),JSON.stringify(coverage,null,2)+'\n');

  let index = '# Choose a seller problem, then follow its data end to end\n\n';
  index += 'Start with the question you want to answer. Each guide follows the same sequence: **raw input → shared core → mart calculation → agent input → seller action example → verification data**. The examples use real generated records and executed SQL results. Planning options and verification targets are explicitly illustrative.\n\n';
  index += '| Seller question | Main mart | End-to-end guide |\n|---|---|---|\n';
  for (const item of cases) index += `| ${playbooks[item.issue_type].question} | ${item.mart_views.length ? item.mart_views.map(name => '`mart.'+name+'`').join(', ') : 'Direct core rule → `mart.issue_candidates`'} | [Walk through this case](use-cases/${item.issue_type}.md) |\n`;
  index += '| How did each shop perform today? | `mart.shop_daily` | [Daily report](use-cases/daily_summary.md) |\n';
  index += '| Why is there no alert? | Capabilities, completeness and sample checks | [Healthy and missing-data controls](use-cases/controls.md) |\n\n';
  index += '## Where each mart fits\n\n| Mart | What it measures | Used by |\n|---|---|---|\n';
  const martPurpose = {
    order_economics: ['Per-order sales, cost, margin and payout variance','Offer loss, fees, payout reconciliation, daily summaries'],
    shop_daily: ['Local daily counts and known financial totals','Seller digest and agency dashboard'],
    shop_window_metrics: ['Recent/baseline cancellation, return and fee rates','Cancellations, returns, fee increases'],
    product_review_metrics: ['Product review rates, repeated sizing text and evidence','Negative review and sizing investigation'],
    inventory_risk: ['Latest stock, seven-day demand and coverage','Stockout prevention'],
    promotion_performance: ['Known margin and loss counts for linked offers','Offer investigation'],
    issue_candidates: ['Rule-matched issues with stable IDs','All nine alert types; shipping/health read core directly'],
    agent_context: ['Portable evidence packet with source/window context','Classification and planning for each alert'],
  };
  for (const [name,[purpose,used]] of Object.entries(martPurpose)) index += `| \`mart.${name}\` | ${purpose} | ${used} |\n`;
  index += '\n## Reading an example\n\nThe main worked record uses Shopee shop `1001`; expandable raw comparisons show Lazada and Shopify. Review, finance, stock and health source records are explicitly demo supplements. Shopee order fields remain provisional. Different connectors produce the same business columns while preserving shop IDs, native identifiers and meaningful status differences.\n\n';
  index += 'The reference clock is **October 31, 2026 at 00:00 Vietnam time**. A few displayed records illustrate the transformation; rates and totals are calculated from the full 14-day dataset. New post-action observations are needed to verify an action.\n\n';
  index += '## Data files and detailed references\n\n'+
    '- [Platform mapping basics](platform-mapping.md): compare the three order formats.\n'+
    '- [Complete reference](reference.md): all 286 dictionary samples, full record examples and every edge-case output.\n'+
    '- [Case-by-case JSON](cases.json): source, core and agent records for each platform.\n'+
    '- [All core rows](core.json), [all mart rows](mart.json), and [coverage checks](coverage.json).\n'+
    '- Raw batches: [Shopee](raw/shopee-open-platform.json), [Lazada](raw/lazada.json), [Shopify](raw/shopify.json).\n'+
    '- [Future agent records](future-agent-examples.json): illustrative approval/execution/learning examples.\n\n';
  index += '## Rebuild\n\nRun from the repository root:\n\n```powershell\nnpm.cmd run example\n```\n\nUse `npm run example` on macOS/Linux. The command re-normalizes existing fixtures, executes the SQL, regenerates the reference and use-case pages, and checks that all eight marts and all nine issue types are covered. It also retains the healthy control, unsupported Shopify health state and 11 isolated edge cases.\n';
  await writeFile(new URL('README.md',output),index);
}
