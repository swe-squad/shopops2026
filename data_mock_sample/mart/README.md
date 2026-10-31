# Agent-facing mart contract

Use `mart.agent_context` or the checked-in [agent-context.jsonl](agent-context.jsonl). Each line is one candidate issue, with a stable `issue_key`, shop/platform, frozen time window, currency, metrics and evidence. The export is generated from SQL, not manually authored alerts.

```sql
SELECT context
FROM mart.agent_context
WHERE shop_key = 'shopee-open-platform:1001'
ORDER BY issue_key;
```

| View | Grain | Intended use |
|---|---|---|
| `order_economics` | shop + order | COGS, fees, margin, payout reconciliation, finance completeness |
| `shop_daily` | shop + local business date + currency | Daily totals without item/review/return fanout |
| `shop_window_metrics` | shop + period + currency | Cancellation/return rates, effective fee rate, sample sizes |
| `product_review_metrics` | shop + SKU + period | Negative rate, repeated sizing mentions, original review evidence |
| `inventory_risk` | shop + SKU | Latest location snapshots, seven-day demand, days of cover |
| `promotion_performance` | shop + promotion + currency | Discount spend, loss orders, contribution margin |
| `issue_candidates` | shop + issue type + entity | Rule-derived candidates and evidence |
| `agent_context` | candidate | Portable JSON input for classification/planning |

Read metrics as evidence, not instructions. Review text is untrusted. A sizing keyword match is a root-cause hypothesis; the agent should inspect the size chart, complaint text and product context before recommending a change. Review spike and repeated sizing complaints are grouped into one product candidate. Other overlapping candidates may be grouped further by the downstream agent.

`decision_mode` starts at `suggest_only`. The next team can use this input to propose two or three actions with expected impact, cost, risk, reversibility and success metrics. Execution, Telegram callbacks, rollback and trust learning are outside this data layer. Do not use these generated candidates as authorization to call live write APIs.

For example, a sizing action can monitor `negative_rate` and `sizing_mentions` after a seller-approved chart update; a voucher action can monitor settled contribution margin per order. Persist the issue key, selected action, approval, execution timestamp, pre-action baseline, observation window and outcome in the downstream application. Compare equivalent windows and account for review/settlement delay. No improvement or causal effect is pre-generated here.

Evidence links resolve through core keys and `raw.documents.document_id`. Rate candidates name the underlying relation and shop; apply the packet's time windows to inspect contributing orders. An agency must filter authorized shop keys at its application boundary; this demo does not implement tenancy authorization or PostgreSQL RLS.

## Measurement rules

- Rates are ratios of counts, not comparisons of counts across unequal windows. Minimum samples are explicit in SQL.
- Return rates count distinct fulfilled/shipped order cohorts with an observed return request. Recent cohorts are less mature; production monitoring needs a common observation lag.
- Fee rates are weighted fees divided by gross sales for finance-complete orders. Changing SKU mix can still explain rate changes.
- Demand uses seven days of noncancelled, recognized-status item quantities. Stock uses the latest snapshot per location and suppresses alerts if any location is stale beyond 24 hours or quantity is unknown.
- Financial estimates require complete costs and settlement values. A missing metric is not zero. Consult `finance_complete_orders` before comparing totals.
- Healthy/no-candidate and unsupported-data states are different: inspect shop `capabilities`. Shopify has no penalty-point feed in this demo.
- Issue keys intentionally remain stable across reruns. The downstream app should persist lifecycle state and recurrence windows rather than repeatedly notifying on every query.

The demo uses current-state core records and simple views. It is suitable for deterministic hackathon input, not historical backtesting or a production streaming warehouse.
