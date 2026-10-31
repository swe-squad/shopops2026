# Did the effective platform fee rate change unexpectedly?

[Back to use-case index](../README.md) · [Complete field reference](../reference.md)

Use this case to answer: **Did the effective platform fee rate change unexpectedly?**

Marts used: `mart.order_economics`, `mart.shop_window_metrics`, `mart.issue_candidates`, `mart.agent_context`. The main calculation is shown below; `issue_candidates` applies the trigger and `agent_context` packages it for the planner.

All measured values below come from the fixed fixture clock, **2026-10-31 00:00 Vietnam time**. Recent window is October 29–30; baseline is October 17–28. The raw/core snippets are representative records; the SQL aggregates use the full source population.

These are administrative fixture queries. For a logged-in user, join `access.user_shop_access` and bind the verified session user ID as shown in the [access guide](../../../access/README.md).

## 1. Source data: what the connector received

The main example uses Shopee shop `1001`. Native order fields are provisional; operational records such as reviews, finance, inventory and health are explicitly labeled demo supplements.

```json
{
  "baseline_order": {
    "currency": "VND",
    "order_sn": "100000",
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
    "create_time": 1792198800,
    "update_time": 1792224000,
    "order_status": "COMPLETED"
  },
  "baseline_settlement": {
    "paid_at": "2026-10-17T15:00:00+07:00",
    "order_id": "100000",
    "fee_amount": 20000,
    "actual_payout": 352000,
    "refund_amount": 0,
    "seller_shipping_cost": 8000
  },
  "recent_order": {
    "currency": "VND",
    "order_sn": "100294",
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
    "create_time": 1793242800,
    "update_time": 1793268000,
    "order_status": "COMPLETED"
  },
  "recent_settlement": {
    "paid_at": "2026-10-29T17:00:00+07:00",
    "order_id": "100294",
    "fee_amount": 30000,
    "actual_payout": 72000,
    "refund_amount": 0,
    "seller_shipping_cost": 8000
  },
  "order_enrichment": [
    {
      "order_id": "100000",
      "promotion_id": null,
      "seller_discount": 20000,
      "platform_discount": 10000
    },
    {
      "order_id": "100294",
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
  "baseline_order": {
    "price": "400000",
    "order_id": 100000,
    "statuses": [
      "delivered"
    ],
    "created_at": "2026-10-17 08:00:00 +0700",
    "updated_at": "2026-10-17 15:00:00 +0700",
    "voucher_seller": "20000",
    "voucher_platform": "10000"
  },
  "baseline_settlement": {
    "paid_at": "2026-10-17T15:00:00+07:00",
    "order_id": "100000",
    "fee_amount": 20000,
    "actual_payout": 352000,
    "refund_amount": 0,
    "seller_shipping_cost": 8000
  },
  "recent_order": {
    "price": "200000",
    "order_id": 100294,
    "statuses": [
      "delivered"
    ],
    "created_at": "2026-10-29 10:00:00 +0700",
    "updated_at": "2026-10-29 17:00:00 +0700",
    "voucher_seller": "90000",
    "voucher_platform": "5000"
  },
  "recent_settlement": {
    "paid_at": "2026-10-29T17:00:00+07:00",
    "order_id": "100294",
    "fee_amount": 30000,
    "actual_payout": 72000,
    "refund_amount": 0,
    "seller_shipping_cost": 8000
  },
  "order_enrichment": [
    {
      "order_id": "100000",
      "promotion_id": null,
      "seller_discount": 20000,
      "platform_discount": 10000
    },
    {
      "order_id": "100294",
      "promotion_id": "SAVE90",
      "seller_discount": 90000,
      "platform_discount": 5000
    }
  ],
  "order_items": [
    {
      "sku": "SHIRT-M",
      "status": "delivered",
      "currency": "VND",
      "order_id": 100000,
      "item_price": "200000",
      "order_item_id": 1000000
    },
    {
      "sku": "SHIRT-M",
      "status": "delivered",
      "currency": "VND",
      "order_id": 100000,
      "item_price": "200000",
      "order_item_id": 1000001
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
  "baseline_order": {
    "id": "gid://shopify/Order/100000",
    "createdAt": "2026-10-17T08:00:00+07:00",
    "lineItems": {
      "nodes": [
        {
          "id": "gid://shopify/LineItem/1000000",
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
    "updatedAt": "2026-10-17T15:00:00+07:00",
    "cancelledAt": null,
    "currencyCode": "VND",
    "discountCodes": [],
    "totalDiscountsSet": {
      "shopMoney": {
        "amount": "20000",
        "currencyCode": "VND"
      }
    },
    "displayFinancialStatus": "PAID",
    "displayFulfillmentStatus": "FULFILLED"
  },
  "baseline_settlement": {
    "paid_at": "2026-10-17T15:00:00+07:00",
    "order_id": "100000",
    "fee_amount": 20000,
    "actual_payout": 352000,
    "refund_amount": 0,
    "seller_shipping_cost": 8000
  },
  "recent_order": {
    "id": "gid://shopify/Order/100294",
    "createdAt": "2026-10-29T10:00:00+07:00",
    "lineItems": {
      "nodes": [
        {
          "id": "gid://shopify/LineItem/1002940",
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
    "updatedAt": "2026-10-29T17:00:00+07:00",
    "cancelledAt": null,
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
    "displayFulfillmentStatus": "FULFILLED"
  },
  "recent_settlement": {
    "paid_at": "2026-10-29T17:00:00+07:00",
    "order_id": "100294",
    "fee_amount": 30000,
    "actual_payout": 72000,
    "refund_amount": 0,
    "seller_shipping_cost": 8000
  },
  "order_enrichment": [
    {
      "order_id": "100000",
      "promotion_id": null,
      "seller_discount": 20000,
      "platform_discount": 0
    },
    {
      "order_id": "100294",
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
  "core.settlements": [
    {
      "shop_key": "shopee-open-platform:1001",
      "order_id": "100000",
      "fee_amount": "20000.00",
      "seller_shipping_cost": "8000.00",
      "refund_amount": "0.00",
      "actual_payout": "352000.00",
      "paid_at": "2026-10-17T08:00:00.000Z"
    },
    {
      "shop_key": "shopee-open-platform:1001",
      "order_id": "100294",
      "fee_amount": "30000.00",
      "seller_shipping_cost": "8000.00",
      "refund_amount": "0.00",
      "actual_payout": "72000.00",
      "paid_at": "2026-10-29T10:00:00.000Z"
    }
  ],
  "core.orders": [
    {
      "shop_key": "shopee-open-platform:1001",
      "order_id": "100000",
      "ordered_at": "2026-10-17T01:00:00.000Z",
      "status": "completed",
      "seller_discount": "20000.00",
      "platform_discount": "10000.00",
      "promotion_id": null
    },
    {
      "shop_key": "shopee-open-platform:1001",
      "order_id": "100294",
      "ordered_at": "2026-10-29T03:00:00.000Z",
      "status": "completed",
      "seller_discount": "90000.00",
      "platform_discount": "5000.00",
      "promotion_id": "SAVE90"
    }
  ],
  "core.order_items": [
    {
      "shop_key": "shopee-open-platform:1001",
      "order_id": "100000",
      "line_id": "100:200",
      "sku": "SHIRT-M",
      "quantity": 2,
      "unit_price": "200000.00",
      "status": "completed"
    },
    {
      "shop_key": "shopee-open-platform:1001",
      "order_id": "100294",
      "line_id": "100:200",
      "sku": "SHIRT-M",
      "quantity": 1,
      "unit_price": "200000.00",
      "status": "completed"
    }
  ]
}
```

## 3. Mart: calculate the measurement

Baseline order 100000: 20,000 fees / 400,000 sales = 5%. Recent order 100294: 30,000 / 200,000 = 15%. The whole-window weighted rates are also 5% and 15%: an increase of 10 percentage points.

Run this query against the loaded PostgreSQL database:

```sql
SELECT shop_key,period,settled_orders,effective_fee_rate
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
    "settled_orders": 276,
    "effective_fee_rate": "0.05000000000000000000"
  },
  {
    "shop_key": "shopee-open-platform:1001",
    "period": "recent",
    "settled_orders": 32,
    "effective_fee_rate": "0.15000000000000000000"
  }
]
```

## 4. Detection and the input passed to the agent

Trigger: At least 10 recent and 20 baseline finance-complete orders and a fee-rate increase greater than 3 percentage points.

Selected fields from the actual `mart.agent_context` packet:

```json
{
  "issue_key": "shopee-open-platform:1001:fee_spike:shop",
  "shop_key": "shopee-open-platform:1001",
  "merchant_id": "merchant-demo-001",
  "platform": "shopee-open-platform",
  "as_of": "2026-10-30T17:00:00+00:00",
  "issue_type": "fee_spike",
  "entity_key": "shop",
  "severity": "medium",
  "metrics": {
    "recent_rate": 0.15,
    "baseline_rate": 0.05,
    "recent_settled_orders": 32,
    "baseline_settled_orders": 276
  },
  "decision_mode": "suggest_only"
}
```

The complete packet, including windows and evidence, is available in `cases.json` and `mart.json`. The planner uses these facts to classify the problem and request missing information.

## 5. Plan → seller chooses → execute

The following are illustrative planning options. The data pipeline has not executed them. Current settings, target IDs, seller approval and connector results must be supplied by the next component.

| Option | Expected purpose / required input | Cost and risk | Reversibility |
|---|---|---|---|
| Reconcile source statements and current fee schedules | Determine whether the change is expected, erroneous, or caused by product mix | Staff time; aggregate fee data has no fee-category breakdown | Read-only investigation requires no rollback |
| Model pricing or campaign changes after reconciliation | Recover margin if a valid recurring fee increase is confirmed | May reduce conversion; requires current prices and campaign terms | Price edits can be restored where the connector supports it |

After the seller chooses an option in Telegram, store the approval under this packet’s `issue_key`, fetch the latest target state, execute idempotently, and retain before/after state and rollback parameters where supported. No numeric impact or success is invented here.

## 6. Verify with new data

Collect new finance-complete settlements, calculate sum(fees) / sum(gross sales), and compare with the confirmed expected schedule and product mix. Do not assume returning to 5% is possible.

**What to collect next:** Compare weighted fees / sales for newly settled orders, accounting for fee schedules and SKU mix.

The frozen fixture contains no post-action success data. Re-querying it proves reproducibility, not action effectiveness.

**Interpretation limits:** An effective rate is an observed aggregate, not an official fee schedule. The fixture has only total fees, so a fee-category explanation requires a new source.

Full source → core → mart samples for each platform: [`cases.json`](../cases.json), find `issue_type = "fee_spike"`. Boundary behavior and unsupported data are explained in the [controls guide](controls.md).
