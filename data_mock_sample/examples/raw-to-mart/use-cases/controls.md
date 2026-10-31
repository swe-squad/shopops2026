# Healthy shops, missing data and boundary behavior

[Back to index](../README.md)

Use these controls to interpret an empty issue list correctly.

## Healthy control

Raw Shopee shop `1002` is normalized through the same adapters and marts. It has normal baseline/recent measurements and no candidates. Its orders and metrics remain visible in `core.json` and `mart.json`.

```json
{
  "shop_key": "shopee-open-platform:1002",
  "candidates": 0
}
```

## Unsupported data

Shopify has no account-health feed in this fixture. An empty health issue list does not demonstrate zero penalty points. Check `core.shops.capabilities` before interpreting missing measurements.

```json
{
  "shop_key": "shopify:1001",
  "capability": "account_health",
  "value": "unsupported",
  "candidates": 0
}
```

## Missing and boundary inputs

The [edge-case samples](../edge-cases.json) show isolated input changes, the SQL used to inspect them and their observed outputs. Each mutation is rolled back.

| Input condition | Expected behavior |
|---|---|
| Missing product cost or fees | Margin stays unknown; no zero-cost assumption. |
| Mixed or unknown order state | Settled-margin eligibility is suppressed pending explicit interpretation. |
| Recognized shipped order with complete settlement | Eligible for financial calculations; does not assert delivery. |
| Unknown stock | Coverage is unknown; no low-stock claim. |
| Known zero stock with demand | Coverage is zero and a stock candidate is emitted. |
| Stale stock | Stock candidate is suppressed until a fresh snapshot is collected. |
| No observed recognized demand | Coverage is unknown; do not divide by zero or invent a forecast. |
| Expired penalty | Event no longer contributes to active-point candidates. |
| Insufficient review sample | Comparison rule waits for enough evidence. |

No candidate can mean healthy, unsupported, unknown, stale or insufficient data. The planner must inspect capabilities, completeness, observation time and sample size before explaining the result to the seller.
