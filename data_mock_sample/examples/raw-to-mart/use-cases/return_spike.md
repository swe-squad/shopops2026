# Are more fulfilled purchases leading to return requests?

[Back to use-case index](../README.md) · [Complete field reference](../reference.md)

Use this case to answer: **Are more fulfilled purchases leading to return requests?**

Marts used: `mart.shop_window_metrics`, `mart.issue_candidates`, `mart.agent_context`. The main calculation is shown below; `issue_candidates` applies the trigger and `agent_context` packages it for the planner.

All measured values below come from the fixed fixture clock, **2026-10-31 00:00 Vietnam time**. Recent window is October 29–30; baseline is October 17–28. The raw/core snippets are representative records; the SQL aggregates use the full source population.

## 1. Source data: what the connector received

The main example uses Shopee shop `1001`. Native order fields are provisional; operational records such as reviews, finance, inventory and health are explicitly labeled demo supplements.

```json
{
  "return": {
    "reason": "Không vừa / đổi ý",
    "status": "refunded",
    "order_id": "100288",
    "return_id": "RT100288",
    "requested_at": "2026-10-29T14:00:00+07:00",
    "refund_amount": 210000
  },
  "order": {
    "currency": "VND",
    "order_sn": "100288",
    "item_list": [
      {
        "item_id": 100,
        "model_id": 200,
        "model_sku": "SHIRT-M",
        "model_original_price": 200000,
        "model_discounted_price": 200000,
        "model_quantity_purchased": 2
      }
    ],
    "create_time": 1793235600,
    "update_time": 1793260800,
    "order_status": "COMPLETED"
  },
  "settlement": {
    "paid_at": "2026-10-29T15:00:00+07:00",
    "order_id": "100288",
    "fee_amount": 60000,
    "actual_payout": -58000,
    "refund_amount": 210000,
    "seller_shipping_cost": 8000
  },
  "order_enrichment": [
    {
      "order_id": "100288",
      "promotion_id": "SAVE90",
      "seller_discount": 180000,
      "platform_discount": 10000
    }
  ]
}
```

<details>
<summary>Compare the raw samples from Lazada and Shopify</summary>

### lazada

```json
{
  "return": {
    "reason": "Không vừa / đổi ý",
    "status": "refunded",
    "order_id": "100288",
    "return_id": "RT100288",
    "requested_at": "2026-10-29T14:00:00+07:00",
    "refund_amount": 210000
  },
  "order": {
    "price": "400000",
    "order_id": 100288,
    "statuses": [
      "delivered"
    ],
    "created_at": "2026-10-29 08:00:00 +0700",
    "updated_at": "2026-10-29 15:00:00 +0700",
    "voucher_seller": "180000",
    "voucher_platform": "10000"
  },
  "settlement": {
    "paid_at": "2026-10-29T15:00:00+07:00",
    "order_id": "100288",
    "fee_amount": 60000,
    "actual_payout": -58000,
    "refund_amount": 210000,
    "seller_shipping_cost": 8000
  },
  "order_enrichment": [
    {
      "order_id": "100288",
      "promotion_id": "SAVE90",
      "seller_discount": 180000,
      "platform_discount": 10000
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
    }
  ]
}
```

### shopify

```json
{
  "return": {
    "reason": "Không vừa / đổi ý",
    "status": "refunded",
    "order_id": "100288",
    "return_id": "RT100288",
    "requested_at": "2026-10-29T14:00:00+07:00",
    "refund_amount": 220000
  },
  "order": {
    "id": "gid://shopify/Order/100288",
    "createdAt": "2026-10-29T08:00:00+07:00",
    "lineItems": {
      "nodes": [
        {
          "id": "gid://shopify/LineItem/1002880",
          "sku": "SHIRT-M",
          "quantity": 2,
          "originalUnitPriceSet": {
            "shopMoney": {
              "amount": "200000",
              "currencyCode": "VND"
            }
          }
        }
      ]
    },
    "updatedAt": "2026-10-29T15:00:00+07:00",
    "cancelledAt": null,
    "currencyCode": "VND",
    "discountCodes": [
      "SAVE90"
    ],
    "totalDiscountsSet": {
      "shopMoney": {
        "amount": "180000",
        "currencyCode": "VND"
      }
    },
    "displayFinancialStatus": "REFUNDED",
    "displayFulfillmentStatus": "FULFILLED"
  },
  "settlement": {
    "paid_at": "2026-10-29T15:00:00+07:00",
    "order_id": "100288",
    "fee_amount": 60000,
    "actual_payout": -68000,
    "refund_amount": 220000,
    "seller_shipping_cost": 8000
  },
  "order_enrichment": [
    {
      "order_id": "100288",
      "promotion_id": "SAVE90",
      "seller_discount": 180000,
      "platform_discount": 0
    }
  ]
}
```

</details>

## 2. General core: the normalized business records

The adapters add `shop_key`, retain source IDs, standardize names/statuses, parse timestamps and convert money to exact decimal values. Use shop + entity ID when joining. The following excerpts contain only fields relevant to this case; full rows retain source-document pointers.

```json
{
  "core.returns": [
    {
      "shop_key": "shopee-open-platform:1001",
      "return_id": "RT100288",
      "order_id": "100288",
      "requested_at": "2026-10-29T07:00:00.000Z",
      "reason": "Không vừa / đổi ý",
      "status": "refunded",
      "refund_amount": "210000.00"
    }
  ],
  "core.orders": [
    {
      "shop_key": "shopee-open-platform:1001",
      "order_id": "100288",
      "ordered_at": "2026-10-29T01:00:00.000Z",
      "status": "completed",
      "seller_discount": "180000.00",
      "platform_discount": "10000.00",
      "promotion_id": "SAVE90"
    }
  ],
  "core.settlements": [
    {
      "shop_key": "shopee-open-platform:1001",
      "order_id": "100288",
      "fee_amount": "60000.00",
      "seller_shipping_cost": "8000.00",
      "refund_amount": "210000.00",
      "actual_payout": "-58000.00",
      "paid_at": "2026-10-29T08:00:00.000Z"
    }
  ]
}
```

## 3. Mart: calculate the measurement

Recent cohort: 10 distinct returned orders / 32 shipped/completed orders = 31.25%. Baseline: 1 / 276 ≈ 0.3623%. A case contributes once per order; its refund amount is already included in settlement financials.

Run this query against the loaded PostgreSQL database:

```sql
SELECT shop_key,period,fulfilled_orders,returned_orders,return_rate
FROM mart.shop_window_metrics
WHERE shop_key='shopee-open-platform:1001'
ORDER BY period;
```

Actual query result:

```json
[
  {
    "shop_key": "shopee-open-platform:1001",
    "period": "baseline",
    "fulfilled_orders": 276,
    "returned_orders": 1,
    "return_rate": "0.00362318840579710145"
  },
  {
    "shop_key": "shopee-open-platform:1001",
    "period": "recent",
    "fulfilled_orders": 32,
    "returned_orders": 10,
    "return_rate": "0.31250000000000000000"
  }
]
```

## 4. Detection and the input passed to the agent

Trigger: At least 10 recent and 20 baseline fulfilled orders, at least 3 returned recent-cohort orders, and recent rate ≥ max(10%, twice baseline).

Selected fields from the actual `mart.agent_context` packet:

```json
{
  "issue_key": "shopee-open-platform:1001:return_spike:shop",
  "shop_key": "shopee-open-platform:1001",
  "platform": "shopee-open-platform",
  "as_of": "2026-10-30T17:00:00+00:00",
  "issue_type": "return_spike",
  "entity_key": "shop",
  "severity": "high",
  "metrics": {
    "caveat": "Order-cohort rates at snapshot time; recent cohorts are less mature",
    "recent_rate": 0.3125,
    "baseline_rate": 0.0036231884057971015,
    "recent_fulfilled_orders": 32,
    "baseline_fulfilled_orders": 276
  },
  "decision_mode": "suggest_only"
}
```

The complete packet, including windows and evidence, is available in `cases.json` and `mart.json`. The planner uses these facts to classify the problem and request missing information.

## 5. Plan → seller chooses → execute

The following are illustrative planning options. The data pipeline has not executed them. Current settings, target IDs, seller approval and connector results must be supplied by the next component.

| Option | Expected purpose / required input | Cost and risk | Reversibility |
|---|---|---|---|
| Review return reasons and inspect affected items | Find whether fit, quality or another issue needs action | Staff inspection cost; current cases are order-level and do not identify returned unit quantities | Investigation requires no rollback |
| Correct confirmed listing or packing issues | Reduce recurrence after evidence confirms a cause | Needs additional listing/packing evidence; changes may have a sales cost | Save prior listing configuration before an editable change |

After the seller chooses an option in Telegram, store the approval under this packet’s `issue_key`, fetch the latest target state, execute idempotently, and retain before/after state and rollback parameters where supported. No numeric impact or success is invented here.

## 6. Verify with new data

Compare distinct returned-order rates in post-action cohorts with the same number of days since purchase. Define minimum sample size and observation lag before judging the outcome.

**What to collect next:** Compare distinct returned-order rates with the same observation lag.

The frozen fixture contains no post-action success data. Re-querying it proves reproducibility, not action effectiveness.

**Interpretation limits:** Recent cohorts have had less time to generate returns. The detector counts observed return requests, not only refunded cases. Shipped/completed is the denominator, not a guaranteed delivered-order count.

Full source → core → mart samples for each platform: [`cases.json`](../cases.json), find `issue_type = "return_spike"`. Boundary behavior and unsupported data are explained in the [controls guide](controls.md).
