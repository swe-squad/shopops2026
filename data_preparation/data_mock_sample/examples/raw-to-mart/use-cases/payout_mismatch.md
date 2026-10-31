# Did this order pay out less than the modeled settlement predicts?

[Back to use-case index](../README.md) · [Complete field reference](../reference.md)

Use this case to answer: **Did this order pay out less than the modeled settlement predicts?**

Marts used: `mart.order_economics`, `mart.issue_candidates`, `mart.agent_context`. The main calculation is shown below; `issue_candidates` applies the trigger and `agent_context` packages it for the planner.

All measured values below come from the fixed fixture clock, **2026-10-31 00:00 Vietnam time**. Recent window is October 29–30; baseline is October 17–28. The raw/core snippets are representative records; the SQL aggregates use the full source population.

These are administrative fixture queries. For a logged-in user, join `access.user_shop_access` and bind the verified session user ID as shown in the [access guide](../../../access/README.md).

## 1. Source data: what the connector received

The main example uses Shopee shop `1001`. Native order fields are provisional; operational records such as reviews, finance, inventory and health are explicitly labeled demo supplements.

```json
{
  "order": {
    "currency": "VND",
    "order_sn": "100296",
    "item_list": [
      {
        "item_id": 102,
        "model_id": 202,
        "model_sku": "TOTE",
        "model_original_price": 250000,
        "model_discounted_price": 250000,
        "model_quantity_purchased": 1
      }
    ],
    "create_time": 1793245200,
    "update_time": 1793270400,
    "order_status": "COMPLETED"
  },
  "settlement": {
    "paid_at": "2026-10-29T17:40:00+07:00",
    "order_id": "100296",
    "fee_amount": 37500,
    "actual_payout": 169500,
    "refund_amount": 0,
    "seller_shipping_cost": 8000
  },
  "order_enrichment": [
    {
      "order_id": "100296",
      "promotion_id": null,
      "seller_discount": 10000,
      "platform_discount": 5000
    }
  ],
  "products": [
    {
      "sku": "TOTE",
      "name": "Túi tote canvas",
      "unit_cost": 120000,
      "cost_basis": "seller_supplied_demo"
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
    "price": "250000",
    "order_id": 100296,
    "statuses": [
      "delivered"
    ],
    "created_at": "2026-10-29 10:40:00 +0700",
    "updated_at": "2026-10-29 17:40:00 +0700",
    "voucher_seller": "10000",
    "voucher_platform": "5000"
  },
  "settlement": {
    "paid_at": "2026-10-29T17:40:00+07:00",
    "order_id": "100296",
    "fee_amount": 37500,
    "actual_payout": 169500,
    "refund_amount": 0,
    "seller_shipping_cost": 8000
  },
  "order_enrichment": [
    {
      "order_id": "100296",
      "promotion_id": null,
      "seller_discount": 10000,
      "platform_discount": 5000
    }
  ],
  "products": [
    {
      "sku": "TOTE",
      "name": "Túi tote canvas",
      "unit_cost": 120000,
      "cost_basis": "seller_supplied_demo"
    }
  ],
  "order_items": [
    {
      "sku": "TOTE",
      "status": "delivered",
      "currency": "VND",
      "order_id": 100296,
      "item_price": "250000",
      "order_item_id": 1002960
    }
  ]
}
```

### shopify

```json
{
  "order": {
    "id": "gid://shopify/Order/100296",
    "createdAt": "2026-10-29T10:40:00+07:00",
    "lineItems": {
      "nodes": [
        {
          "id": "gid://shopify/LineItem/1002960",
          "sku": "TOTE",
          "quantity": 1,
          "originalUnitPriceSet": {
            "shopMoney": {
              "amount": "250000",
              "currencyCode": "VND"
            }
          }
        }
      ]
    },
    "updatedAt": "2026-10-29T17:40:00+07:00",
    "cancelledAt": null,
    "currencyCode": "VND",
    "discountCodes": [],
    "totalDiscountsSet": {
      "shopMoney": {
        "amount": "10000",
        "currencyCode": "VND"
      }
    },
    "displayFinancialStatus": "PAID",
    "displayFulfillmentStatus": "FULFILLED"
  },
  "settlement": {
    "paid_at": "2026-10-29T17:40:00+07:00",
    "order_id": "100296",
    "fee_amount": 37500,
    "actual_payout": 169500,
    "refund_amount": 0,
    "seller_shipping_cost": 8000
  },
  "order_enrichment": [
    {
      "order_id": "100296",
      "promotion_id": null,
      "seller_discount": 10000,
      "platform_discount": 0
    }
  ],
  "products": [
    {
      "sku": "TOTE",
      "name": "Túi tote canvas",
      "unit_cost": 120000,
      "cost_basis": "seller_supplied_demo"
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
      "order_id": "100296",
      "fee_amount": "37500.00",
      "seller_shipping_cost": "8000.00",
      "refund_amount": "0.00",
      "actual_payout": "169500.00",
      "paid_at": "2026-10-29T10:40:00.000Z"
    }
  ],
  "core.orders": [
    {
      "shop_key": "shopee-open-platform:1001",
      "order_id": "100296",
      "ordered_at": "2026-10-29T03:40:00.000Z",
      "status": "completed",
      "seller_discount": "10000.00",
      "platform_discount": "5000.00",
      "promotion_id": null
    }
  ],
  "core.order_items": [
    {
      "shop_key": "shopee-open-platform:1001",
      "order_id": "100296",
      "line_id": "102:202",
      "sku": "TOTE",
      "quantity": 1,
      "unit_price": "250000.00",
      "status": "completed"
    }
  ],
  "core.products": [
    {
      "shop_key": "shopee-open-platform:1001",
      "sku": "TOTE",
      "unit_cost": "120000.00",
      "cost_basis": "seller_supplied_demo"
    }
  ]
}
```

## 3. Mart: calculate the measurement

This order has 250,000 sales − 10,000 seller discount − 37,500 fees − 8,000 shipping − 0 refunds = 194,500 VND expected payout. Actual payout is 169,500 VND. Variance = actual − expected = −25,000 VND.

Run this query against the loaded PostgreSQL database:

```sql
SELECT shop_key,order_id,gross_sales,seller_discount,fee_amount,seller_shipping_cost,refund_amount,expected_payout,actual_payout,payout_variance
FROM mart.order_economics
WHERE shop_key='shopee-open-platform:1001'
  AND order_id='100296';
```

Actual query result:

```json
[
  {
    "shop_key": "shopee-open-platform:1001",
    "order_id": "100296",
    "gross_sales": "250000.00",
    "seller_discount": "10000.00",
    "fee_amount": "37500.00",
    "seller_shipping_cost": "8000.00",
    "refund_amount": "0.00",
    "expected_payout": "194500.00",
    "actual_payout": "169500.00",
    "payout_variance": "-25000.00"
  }
]
```

## 4. Detection and the input passed to the agent

Trigger: Absolute payout variance exceeds 1,000 VND and the settlement falls in the recent window.

Selected fields from the actual `mart.agent_context` packet:

```json
{
  "issue_key": "shopee-open-platform:1001:payout_mismatch:100296",
  "shop_key": "shopee-open-platform:1001",
  "merchant_id": "merchant-demo-001",
  "platform": "shopee-open-platform",
  "as_of": "2026-10-30T17:00:00+00:00",
  "issue_type": "payout_mismatch",
  "entity_key": "100296",
  "severity": "high",
  "metrics": {
    "currency": "VND",
    "variance": -25000,
    "actual_payout": 169500,
    "expected_payout": 194500
  },
  "decision_mode": "suggest_only"
}
```

The complete packet, including windows and evidence, is available in `cases.json` and `mart.json`. The planner uses these facts to classify the problem and request missing information.

## 5. Plan → seller chooses → execute

The following are illustrative planning options. The data pipeline has not executed them. Current settings, target IDs, seller approval and connector results must be supplied by the next component.

| Option | Expected purpose / required input | Cost and risk | Reversibility |
|---|---|---|---|
| Fetch detailed adjustments and fee lines for this order | Check whether an omitted legitimate adjustment explains the shortfall | Staff/API cost; the current fixture does not provide adjustment details | Read-only investigation requires no rollback |
| Prepare a reconciliation case for seller review | Give the seller a traceable order-level evidence bundle | Outcome and recovery are unknown; submitting a case is a separate approved action | An external submission may not be reversible |

After the seller chooses an option in Telegram, store the approval under this packet’s `issue_key`, fetch the latest target state, execute idempotently, and retain before/after state and rollback parameters where supported. No numeric impact or success is invented here.

## 6. Verify with new data

Fetch a new source statement or adjustment. Recompute expected and actual payout and check whether the discrepancy is explained or corrected. Preserve the original evidence for comparison.

**What to collect next:** Reconcile a new statement or adjustment and check whether the order variance closes.

The frozen fixture contains no post-action success data. Re-querying it proves reproducibility, not action effectiveness.

**Interpretation limits:** The discrepancy is against this simplified model. Missing taxes, adjustments or shipping pass-throughs can explain differences in live data; it does not prove the platform underpaid.

Full source → core → mart samples for each platform: [`cases.json`](../cases.json), find `issue_type = "payout_mismatch"`. Boundary behavior and unsupported data are explained in the [controls guide](controls.md).
