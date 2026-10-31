# Choose a seller problem, then follow its data end to end

Start with the question you want to answer. Each guide follows the same sequence: **raw input → shared core → mart calculation → agent input → seller action example → verification data**. The examples use real generated records and executed SQL results. Planning options and verification targets are explicitly illustrative.

| Seller question | Main mart | End-to-end guide |
|---|---|---|
| Why are buyers suddenly complaining that this shirt is too small? | `mart.product_review_metrics` | [Walk through this case](use-cases/product_reviews.md) |
| Is the SAVE90 offer associated with orders that lose money? | `mart.order_economics`, `mart.promotion_performance` | [Walk through this case](use-cases/promotion_loss.md) |
| Are unusually many newly placed orders being cancelled? | `mart.shop_window_metrics` | [Walk through this case](use-cases/cancellation_spike.md) |
| Are more fulfilled purchases leading to return requests? | `mart.shop_window_metrics` | [Walk through this case](use-cases/return_spike.md) |
| Did the effective platform fee rate change unexpectedly? | `mart.order_economics`, `mart.shop_window_metrics` | [Walk through this case](use-cases/fee_spike.md) |
| Did this order pay out less than the modeled settlement predicts? | `mart.order_economics` | [Walk through this case](use-cases/payout_mismatch.md) |
| Will the popular shirt sell out before the seller replenishes it? | `mart.inventory_risk` | [Walk through this case](use-cases/low_stock.md) |
| Which open orders need dispatch attention now? | Direct core rule → `mart.issue_candidates` | [Walk through this case](use-cases/shipment_risk.md) |
| Does the seller have active penalty events that need attention? | Direct core rule → `mart.issue_candidates` | [Walk through this case](use-cases/account_health.md) |
| How did each shop perform today? | `mart.shop_daily` | [Daily report](use-cases/daily_summary.md) |
| Why is there no alert? | Capabilities, completeness and sample checks | [Healthy and missing-data controls](use-cases/controls.md) |

## Where each mart fits

| Mart | What it measures | Used by |
|---|---|---|
| `mart.order_economics` | Per-order sales, cost, margin and payout variance | Offer loss, fees, payout reconciliation, daily summaries |
| `mart.shop_daily` | Local daily counts and known financial totals | Seller digest and agency dashboard |
| `mart.shop_window_metrics` | Recent/baseline cancellation, return and fee rates | Cancellations, returns, fee increases |
| `mart.product_review_metrics` | Product review rates, repeated sizing text and evidence | Negative review and sizing investigation |
| `mart.inventory_risk` | Latest stock, seven-day demand and coverage | Stockout prevention |
| `mart.promotion_performance` | Known margin and loss counts for linked offers | Offer investigation |
| `mart.issue_candidates` | Rule-matched issues with stable IDs | All nine alert types; shipping/health read core directly |
| `mart.agent_context` | Portable evidence packet with source/window context | Classification and planning for each alert |

## Reading an example

The main worked record uses Shopee shop `1001`; expandable raw comparisons show Lazada and Shopify. Review, finance, stock and health source records are explicitly demo supplements. Shopee order fields remain provisional. Different connectors produce the same business columns while preserving shop IDs, native identifiers and meaningful status differences.

The reference clock is **October 31, 2026 at 00:00 Vietnam time**. A few displayed records illustrate the transformation; rates and totals are calculated from the full 14-day dataset. New post-action observations are needed to verify an action.

## Data files and detailed references

- [Platform mapping basics](platform-mapping.md): compare the three order formats.
- [Complete reference](reference.md): all dictionary samples, full record examples and every edge-case output.
- [User shop access](../../access/README.md) and [access rows/results](access.json): users, merchant ownership, memberships and allowed shops.
- [Case-by-case JSON](cases.json): source, core and agent records for each platform.
- [All core rows](core.json), [all mart rows](mart.json), and [coverage checks](coverage.json).
- Raw batches: [Shopee](raw/shopee-open-platform.json), [Lazada](raw/lazada.json), [Shopify](raw/shopify.json).
- [Future agent records](future-agent-examples.json): illustrative approval/execution/learning examples.

## Rebuild

Run from `data_mock_sample`:

```powershell
npm.cmd install
npm.cmd test
npm.cmd run example
```

Use `npm` on macOS/Linux. Tests normalize the fixtures and validate PostgreSQL results. The example command reloads the generated seed, regenerates the reference and use-case pages, and checks that all eight marts and all nine issue types are covered. It also retains the healthy control, unsupported Shopify health state and 11 isolated edge cases.
