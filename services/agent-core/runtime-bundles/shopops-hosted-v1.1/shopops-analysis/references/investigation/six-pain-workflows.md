# Six seller investigation workflows

Choose evidence for the question, not every workflow at once. These are diagnostic recipes, never
claims that the current tool set supports each mart/raw record. Today's tools cover only scoped
fixture returns/review summaries plus versioned knowledge and current-conversation history. For
missing reads/refresh/operations, state the gap; use the names actually granted by a future schema.

| Workflow | Mart/summary first | Permitted raw drilldown to test the hypothesis | Safe next step and outcome check |
| --- | --- | --- | --- |
| Review complaints and returns | Product/variant review themes, counts, return counts/rate and comparable baseline | Review text and date, order/return reason, variant and relevant listing/fulfilment evidence; distinguish requested/approved/received return states | Separate sizing/quality/description/handling hypotheses. Offer listing or fulfilment options as proposals; verify complaint/return metrics in a comparable later interval. |
| Voucher margin leakage | Net contribution by product/order/campaign after discounts, fees and cost inputs | Order lines, voucher funding/stacking rules, fees, refunds and cost records | Check missing costs before calling an order loss-making. Compare campaign options with estimates; stopping/editing a voucher is a separate write requiring approval. Verify net contribution and conversion after an authorized change. |
| Cancellations and late shipments | Cancellation and late-dispatch rates by product, status, carrier and comparable dates | Order lifecycle timestamps, cancellation actor/reason, dispatch deadline and carrier handoff | Distinguish seller delay, buyer cancellation and carrier delay; do not infer one from totals. Propose operational checks and verify cancellation/on-time dispatch over a defined observation window. |
| Inventory versus demand | Available/reserved stock, sales velocity and stockout exposure by variant | Stock snapshots/movements, reservations, inbound receipts and order demand timestamps | Check stock age, reservation semantics and demand coverage before projecting stockout. Explain assumptions; stock/purchase/listing updates require separate authority. Verify actual availability and fulfilment. |
| Penalties and account health | Penalty points/notices and dated operational signals | Versioned policy, notice detail, relevant order/shipment records and appeal deadline | Match the policy version and exact affected orders; do not promise reversal or treat a correlation as a violation. Present evidence/appeal options, then verify the platform's authoritative notice/result. |
| Payout and fee anomalies | Settlements, fees/refunds and expected-versus-received totals by period | Settlement ledger, order lines, fee rules, adjustments and payout timing | Distinguish pending settlement, recognized charge, refund and confirmed discrepancy. Missing ledger coverage is not missing money. Propose reconciliation and verify authoritative settlement receipts. |

For every workflow, keep authorized scope, query dates, observed_at, revision and coverage visible.
Use the [freshness lifecycle](refresh-and-freshness.md) if granted pull-latest is needed. Raw records
can refute a hypothesis; a summary spike is not a cause. Preserve evidence when source definitions
or revisions disagree and seek a scoped reread. Expose remaining uncertainty in Vietnamese.

For compound returns artifacts use the existing returns-analysis/knowledge-review skills and
data-analyst/knowledge-analyst roles. The closed report-v1 supports return metrics and policy findings
only. Broader recipes may inform text responses from actual granted evidence; they do not add keys
to report-v1 or make review categories a new authoritative source. End with 2–3 relevant options
when evidence supports them, their expected impact/cost/risk/reversibility, and a verification metric
and window. Today's read-only capabilities can propose these actions, never execute them.
