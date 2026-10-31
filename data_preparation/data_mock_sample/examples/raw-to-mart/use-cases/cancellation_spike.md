# Are unusually many newly placed orders being cancelled?

[Back to use-case index](../README.md) · [Complete field reference](../reference.md)

Use this case to answer: **Are unusually many newly placed orders being cancelled?**

Marts used: `mart.shop_window_metrics`, `mart.issue_candidates`, `mart.agent_context`. The main calculation is shown below; `issue_candidates` applies the trigger and `agent_context` packages it for the planner.

All measured values below come from the fixed fixture clock, **2026-10-31 00:00 Vietnam time**. Recent window is October 29–30; baseline is October 17–28. The raw/core snippets are representative records; the SQL aggregates use the full source population.

These are administrative fixture queries. For a logged-in user, join `access.user_shop_access` and bind the verified session user ID as shown in the [access guide](../../../access/README.md).

## 1. Source data: what the connector received

The main example uses Shopee shop `1001`. Native order fields are provisional; operational records such as reviews, finance, inventory and health are explicitly labeled demo supplements.

```json
{
  "order": {
    "currency": "VND",
    "order_sn": "100306",
    "item_list": [
      {
        "item_id": 100,
        "model_id": 200,
        "model_sku": "SHIRT-M",
        "model_original_price": 200000,
        "model_discounted_price": 200000,
        "model_quantity_purchased": 1
      }
    ],
    "create_time": 1793257200,
    "update_time": 1793282400,
    "order_status": "CANCELLED"
  },
  "order_enrichment": [
    {
      "order_id": "100306",
      "promotion_id": "SAVE90",
      "seller_discount": 90000,
      "platform_discount": 5000
    }
  ]
}
```

<details>
<summary>Compare the raw samples from Lazada and Shopify</summary>

### lazada

```json
{
  "order": {
    "price": "200000",
    "order_id": 100306,
    "statuses": [
      "canceled"
    ],
    "created_at": "2026-10-29 14:00:00 +0700",
    "updated_at": "2026-10-29 21:00:00 +0700",
    "voucher_seller": "90000",
    "voucher_platform": "5000"
  },
  "order_enrichment": [
    {
      "order_id": "100306",
      "promotion_id": "SAVE90",
      "seller_discount": 90000,
      "platform_discount": 5000
    }
  ],
  "order_items": [
    {
      "sku": "SHIRT-M",
      "status": "canceled",
      "currency": "VND",
      "order_id": 100306,
      "item_price": "200000",
      "order_item_id": 1003060
    }
  ]
}
```

### shopify

```json
{
  "order": {
    "id": "gid://shopify/Order/100306",
    "createdAt": "2026-10-29T14:00:00+07:00",
    "lineItems": {
      "nodes": [
        {
          "id": "gid://shopify/LineItem/1003060",
          "sku": "SHIRT-M",
          "quantity": 1,
          "originalUnitPriceSet": {
            "shopMoney": {
              "amount": "200000",
              "currencyCode": "VND"
            }
          }
        }
      ]
    },
    "updatedAt": "2026-10-29T21:00:00+07:00",
    "cancelledAt": "2026-10-29T14:30:00+07:00",
    "currencyCode": "VND",
    "discountCodes": [
      "SAVE90"
    ],
    "totalDiscountsSet": {
      "shopMoney": {
        "amount": "90000",
        "currencyCode": "VND"
      }
    },
    "displayFinancialStatus": "PAID",
    "displayFulfillmentStatus": "UNFULFILLED"
  },
  "order_enrichment": [
    {
      "order_id": "100306",
      "promotion_id": "SAVE90",
      "seller_discount": 90000,
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
  "core.orders": [
    {
      "shop_key": "shopee-open-platform:1001",
      "order_id": "100306",
      "ordered_at": "2026-10-29T07:00:00.000Z",
      "status": "cancelled",
      "seller_discount": "90000.00",
      "platform_discount": "5000.00",
      "promotion_id": "SAVE90"
    }
  ]
}
```

## 3. Mart: calculate the measurement

Recent: 12 cancelled orders / 48 orders = 25%. Baseline: 12 / 288 = 4.1667%. The recent rate is six times the baseline. Count orders once, regardless of how many item rows they contain.

Run this query against the loaded PostgreSQL database:

```sql
SELECT shop_key,period,orders,cancelled_orders,cancellation_rate
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
    "orders": 288,
    "cancelled_orders": 12,
    "cancellation_rate": "0.04166666666666666667"
  },
  {
    "shop_key": "shopee-open-platform:1001",
    "period": "recent",
    "orders": 48,
    "cancelled_orders": 12,
    "cancellation_rate": "0.25000000000000000000"
  }
]
```

## 4. Detection and the input passed to the agent

Trigger: At least 10 recent and 20 baseline orders, at least 3 recent cancellations, and recent rate ≥ max(10%, twice baseline).

Selected fields from the actual `mart.agent_context` packet:

```json
{
  "issue_key": "shopee-open-platform:1001:cancellation_spike:shop",
  "shop_key": "shopee-open-platform:1001",
  "merchant_id": "merchant-demo-001",
  "platform": "shopee-open-platform",
  "as_of": "2026-10-30T17:00:00+00:00",
  "issue_type": "cancellation_spike",
  "entity_key": "shop",
  "severity": "high",
  "metrics": {
    "recent_rate": 0.25,
    "baseline_rate": 0.041666666666666664,
    "recent_orders": 48,
    "baseline_orders": 288
  },
  "decision_mode": "suggest_only"
}
```

The complete packet, including windows and evidence, is available in `cases.json` and `mart.json`. The planner uses these facts to classify the problem and request missing information.

## 5. Plan → seller chooses → execute

The following are illustrative planning options. The data pipeline has not executed them. Current settings, target IDs, seller approval and connector results must be supplied by the next component.

| Option | Expected purpose / required input | Cost and risk | Reversibility |
|---|---|---|---|
| Review recent cancelled orders and collect cancellation reasons | Identify whether stock, fulfillment or buyer choice drives cancellations | Staff review time; current fixtures do not include cancellation reason codes | Read-only investigation requires no rollback |
| Reconcile availability for affected SKUs before changing listings | Reduce avoidable cancellations if stock mismatch is confirmed | Requires new stock evidence; unnecessary listing changes may reduce sales | Listing availability can be restored if supported |

After the seller chooses an option in Telegram, store the approval under this packet’s `issue_key`, fetch the latest target state, execute idempotently, and retain before/after state and rollback parameters where supported. No numeric impact or success is invented here.

## 6. Verify with new data

Measure cancelled / all orders in a new post-action cohort. Example target: below 10% over at least 50 new orders, with a comparable cancellation observation delay.

**What to collect next:** Compare cancelled orders / all orders in equivalent post-action order cohorts.

The frozen fixture contains no post-action success data. Re-querying it proves reproducibility, not action effectiveness.

**Interpretation limits:** The data proves a rate change, but does not establish why orders were cancelled. Do not infer stock problems from cancellation counts alone.

Full source → core → mart samples for each platform: [`cases.json`](../cases.json), find `issue_type = "cancellation_spike"`. Boundary behavior and unsupported data are explained in the [controls guide](controls.md).
