# Why are buyers suddenly complaining that this shirt is too small?

[Back to use-case index](../README.md) · [Complete field reference](../reference.md)

Use this case to answer: **Why are buyers suddenly complaining that this shirt is too small?**

Marts used: `mart.product_review_metrics`, `mart.issue_candidates`, `mart.agent_context`. The main calculation is shown below; `issue_candidates` applies the trigger and `agent_context` packages it for the planner.

All measured values below come from the fixed fixture clock, **2026-10-31 00:00 Vietnam time**. Recent window is October 29–30; baseline is October 17–28. The raw/core snippets are representative records; the SQL aggregates use the full source population.

## 1. Source data: what the connector received

The main example uses Shopee shop `1001`. Native order fields are provisional; operational records such as reviews, finance, inventory and health are explicitly labeled demo supplements.

```json
{
  "reviews": [
    {
      "sku": "SHIRT-M",
      "body": "Áo quá chật, size M nhỏ hơn bảng size.",
      "rating": 1,
      "order_id": "100288",
      "review_id": "R100288",
      "reviewed_at": "2026-10-29T12:00:00+07:00"
    },
    {
      "sku": "SHIRT-M",
      "body": "Áo quá chật, size M nhỏ hơn bảng size.",
      "rating": 1,
      "order_id": "100291",
      "review_id": "R100291",
      "reviewed_at": "2026-10-29T13:00:00+07:00"
    },
    {
      "sku": "SHIRT-M",
      "body": "Áo quá chật, size M nhỏ hơn bảng size.",
      "rating": 1,
      "order_id": "100294",
      "review_id": "R100294",
      "reviewed_at": "2026-10-29T14:00:00+07:00"
    }
  ]
}
```

<details>
<summary>Compare the raw samples from Lazada and Shopify</summary>

### lazada

```json
{
  "reviews": [
    {
      "sku": "SHIRT-M",
      "body": "Áo quá chật, size M nhỏ hơn bảng size.",
      "rating": 1,
      "order_id": "100288",
      "review_id": "R100288",
      "reviewed_at": "2026-10-29T12:00:00+07:00"
    },
    {
      "sku": "SHIRT-M",
      "body": "Áo quá chật, size M nhỏ hơn bảng size.",
      "rating": 1,
      "order_id": "100291",
      "review_id": "R100291",
      "reviewed_at": "2026-10-29T13:00:00+07:00"
    },
    {
      "sku": "SHIRT-M",
      "body": "Áo quá chật, size M nhỏ hơn bảng size.",
      "rating": 1,
      "order_id": "100294",
      "review_id": "R100294",
      "reviewed_at": "2026-10-29T14:00:00+07:00"
    }
  ],
  "order_items": [
    {
      "sku": "SHIRT-M",
      "status": "delivered",
      "currency": "VND",
      "order_id": 100288,
      "item_price": "200000",
      "order_item_id": 1002880
    },
    {
      "sku": "SHIRT-M",
      "status": "delivered",
      "currency": "VND",
      "order_id": 100288,
      "item_price": "200000",
      "order_item_id": 1002881
    },
    {
      "sku": "SHIRT-M",
      "status": "delivered",
      "currency": "VND",
      "order_id": 100291,
      "item_price": "200000",
      "order_item_id": 1002910
    },
    {
      "sku": "SHIRT-M",
      "status": "delivered",
      "currency": "VND",
      "order_id": 100294,
      "item_price": "200000",
      "order_item_id": 1002940
    }
  ]
}
```

### shopify

```json
{
  "reviews": [
    {
      "sku": "SHIRT-M",
      "body": "Áo quá chật, size M nhỏ hơn bảng size.",
      "rating": 1,
      "order_id": "100288",
      "review_id": "R100288",
      "reviewed_at": "2026-10-29T12:00:00+07:00"
    },
    {
      "sku": "SHIRT-M",
      "body": "Áo quá chật, size M nhỏ hơn bảng size.",
      "rating": 1,
      "order_id": "100291",
      "review_id": "R100291",
      "reviewed_at": "2026-10-29T13:00:00+07:00"
    },
    {
      "sku": "SHIRT-M",
      "body": "Áo quá chật, size M nhỏ hơn bảng size.",
      "rating": 1,
      "order_id": "100294",
      "review_id": "R100294",
      "reviewed_at": "2026-10-29T14:00:00+07:00"
    }
  ]
}
```

</details>

## 2. General core: the normalized business records

The adapters add `shop_key`, retain source IDs, standardize names/statuses, parse timestamps and convert money to exact decimal values. Use shop + entity ID when joining. The following excerpts contain only fields relevant to this case; full rows retain source-document pointers.

```json
{
  "core.reviews": [
    {
      "shop_key": "shopee-open-platform:1001",
      "review_id": "R100288",
      "order_id": "100288",
      "sku": "SHIRT-M",
      "reviewed_at": "2026-10-29T05:00:00.000Z",
      "rating": 1,
      "body": "Áo quá chật, size M nhỏ hơn bảng size."
    },
    {
      "shop_key": "shopee-open-platform:1001",
      "review_id": "R100291",
      "order_id": "100291",
      "sku": "SHIRT-M",
      "reviewed_at": "2026-10-29T06:00:00.000Z",
      "rating": 1,
      "body": "Áo quá chật, size M nhỏ hơn bảng size."
    },
    {
      "shop_key": "shopee-open-platform:1001",
      "review_id": "R100294",
      "order_id": "100294",
      "sku": "SHIRT-M",
      "reviewed_at": "2026-10-29T07:00:00.000Z",
      "rating": 1,
      "body": "Áo quá chật, size M nhỏ hơn bảng size."
    }
  ]
}
```

## 3. Mart: calculate the measurement

Negative-review rate = one/two-star reviews / all reviews. The recent shirt cohort has 11 / 11 = 100%; baseline has 3 / 96 = 3.125%. All 11 recent negatives contain sizing keywords. These measurements support one product issue with two triggers.

Run this query against the loaded PostgreSQL database:

```sql
SELECT shop_key,sku,period,reviews,negative_reviews,negative_rate,sizing_mentions
FROM mart.product_review_metrics
WHERE shop_key='shopee-open-platform:1001'
  AND sku='SHIRT-M'
ORDER BY period;
```

Actual query result:

```json
[
  {
    "shop_key": "shopee-open-platform:1001",
    "sku": "SHIRT-M",
    "period": "baseline",
    "reviews": 96,
    "negative_reviews": 3,
    "negative_rate": "0.03125000000000000000",
    "sizing_mentions": 3
  },
  {
    "shop_key": "shopee-open-platform:1001",
    "sku": "SHIRT-M",
    "period": "recent",
    "reviews": 11,
    "negative_reviews": 11,
    "negative_rate": "1.00000000000000000000",
    "sizing_mentions": 11
  }
]
```

## 4. Detection and the input passed to the agent

Trigger: At least 5 recent and 10 baseline reviews; at least 3 recent negatives; recent negative rate ≥ max(20%, twice baseline). Three sizing mentions add the repeated-sizing trigger.

Selected fields from the actual `mart.agent_context` packet:

```json
{
  "issue_key": "shopee-open-platform:1001:product_reviews:SHIRT-M",
  "shop_key": "shopee-open-platform:1001",
  "platform": "shopee-open-platform",
  "as_of": "2026-10-30T17:00:00+00:00",
  "issue_type": "product_reviews",
  "entity_key": "SHIRT-M",
  "severity": "high",
  "metrics": {
    "triggers": [
      "negative_review_spike",
      "repeated_sizing_complaint"
    ],
    "negative_rate": 1,
    "recent_reviews": 11,
    "sizing_mentions": 11,
    "baseline_reviews": 96,
    "root_cause_hypothesis": "Product sizing runs small; inspect size chart",
    "baseline_negative_rate": 0.03125
  },
  "decision_mode": "suggest_only"
}
```

The complete packet, including windows and evidence, is available in `cases.json` and `mart.json`. The planner uses these facts to classify the problem and request missing information.

## 5. Plan → seller chooses → execute

The following are illustrative planning options. The data pipeline has not executed them. Current settings, target IDs, seller approval and connector results must be supplied by the next component.

| Option | Expected purpose / required input | Cost and risk | Reversibility |
|---|---|---|---|
| Inspect stock measurements and correct the size guide if wrong | Reduce expectation mismatch; requires staff measurement and current chart | Low direct cost; benefit needs later evidence | Listing text/chart edits may be reverted if the original state is saved |
| Add a seller-approved fit warning | Help buyers choose a size; requires current listing content | Could reduce conversion; impact is unknown | Listing text can be restored from the saved before-state |

After the seller chooses an option in Telegram, store the approval under this packet’s `issue_key`, fetch the latest target state, execute idempotently, and retain before/after state and rollback parameters where supported. No numeric impact or success is invented here.

## 6. Verify with new data

Collect new reviews for orders placed after the listing change, allow review delay, and compare negative sizing-review rates with an explicit minimum sample. Example success criterion: below 10% after 20 eligible reviews. This criterion is illustrative; no successful outcome is pre-generated.

**What to collect next:** Compare post-change sizing-review rates for purchases exposed to the new listing after sufficient review delay.

The frozen fixture contains no post-action success data. Re-querying it proves reproducibility, not action effectiveness.

**Interpretation limits:** Keyword matches suggest a sizing problem; the current data does not include the actual size chart or prove a manufacturing defect.

Full source → core → mart samples for each platform: [`cases.json`](../cases.json), find `issue_type = "product_reviews"`. Boundary behavior and unsupported data are explained in the [controls guide](controls.md).
