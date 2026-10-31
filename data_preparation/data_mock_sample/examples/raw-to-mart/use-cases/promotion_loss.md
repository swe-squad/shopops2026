# Is the SAVE90 offer associated with orders that lose money?

[Back to use-case index](../README.md) · [Complete field reference](../reference.md)

Use this case to answer: **Is the SAVE90 offer associated with orders that lose money?**

Marts used: `mart.order_economics`, `mart.promotion_performance`, `mart.issue_candidates`, `mart.agent_context`. The main calculation is shown below; `issue_candidates` applies the trigger and `agent_context` packages it for the planner.

All measured values below come from the fixed fixture clock, **2026-10-31 00:00 Vietnam time**. Recent window is October 29–30; baseline is October 17–28. The raw/core snippets are representative records; the SQL aggregates use the full source population.

These are administrative fixture queries. For a logged-in user, join `access.user_shop_access` and bind the verified session user ID as shown in the [access guide](../../../access/README.md).

## 1. Source data: what the connector received

The main example uses Shopee shop `1001`. Native order fields are provisional; operational records such as reviews, finance, inventory and health are explicitly labeled demo supplements.

```json
{
  "order": {
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
  "enrichment": {
    "order_id": "100294",
    "promotion_id": "SAVE90",
    "seller_discount": 90000,
    "platform_discount": 5000
  },
  "product": {
    "sku": "SHIRT-M",
    "name": "Áo thun cotton size M",
    "unit_cost": 130000,
    "cost_basis": "seller_supplied_demo"
  },
  "promotion": {
    "name": "Giảm 90k cho áo thun",
    "ends_at": "2026-11-05T00:00:00+07:00",
    "funding": "seller",
    "starts_at": "2026-10-29T00:00:00+07:00",
    "promotion_id": "SAVE90"
  },
  "settlement": {
    "paid_at": "2026-10-29T17:00:00+07:00",
    "order_id": "100294",
    "fee_amount": 30000,
    "actual_payout": 72000,
    "refund_amount": 0,
    "seller_shipping_cost": 8000
  },
  "order_enrichment": [
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
  "order": {
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
  "enrichment": {
    "order_id": "100294",
    "promotion_id": "SAVE90",
    "seller_discount": 90000,
    "platform_discount": 5000
  },
  "product": {
    "sku": "SHIRT-M",
    "name": "Áo thun cotton size M",
    "unit_cost": 130000,
    "cost_basis": "seller_supplied_demo"
  },
  "promotion": {
    "name": "Giảm 90k cho áo thun",
    "ends_at": "2026-11-05T00:00:00+07:00",
    "funding": "seller",
    "starts_at": "2026-10-29T00:00:00+07:00",
    "promotion_id": "SAVE90"
  },
  "settlement": {
    "paid_at": "2026-10-29T17:00:00+07:00",
    "order_id": "100294",
    "fee_amount": 30000,
    "actual_payout": 72000,
    "refund_amount": 0,
    "seller_shipping_cost": 8000
  },
  "order_enrichment": [
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
  "order": {
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
  "enrichment": {
    "order_id": "100294",
    "promotion_id": "SAVE90",
    "seller_discount": 90000,
    "platform_discount": 0
  },
  "product": {
    "sku": "SHIRT-M",
    "name": "Áo thun cotton size M",
    "unit_cost": 130000,
    "cost_basis": "seller_supplied_demo"
  },
  "promotion": {
    "name": "Giảm 90k cho áo thun",
    "ends_at": "2026-11-05T00:00:00+07:00",
    "funding": "seller",
    "starts_at": "2026-10-29T00:00:00+07:00",
    "promotion_id": "SAVE90"
  },
  "settlement": {
    "paid_at": "2026-10-29T17:00:00+07:00",
    "order_id": "100294",
    "fee_amount": 30000,
    "actual_payout": 72000,
    "refund_amount": 0,
    "seller_shipping_cost": 8000
  },
  "order_enrichment": [
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
  "core.orders": [
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
      "order_id": "100294",
      "line_id": "100:200",
      "sku": "SHIRT-M",
      "quantity": 1,
      "unit_price": "200000.00",
      "status": "completed"
    }
  ],
  "core.products": [
    {
      "shop_key": "shopee-open-platform:1001",
      "sku": "SHIRT-M",
      "unit_cost": "130000.00",
      "cost_basis": "seller_supplied_demo"
    }
  ],
  "core.promotions": [
    {
      "shop_key": "shopee-open-platform:1001",
      "promotion_id": "SAVE90",
      "funding": "seller",
      "starts_at": "2026-10-28T17:00:00.000Z",
      "ends_at": "2026-11-04T17:00:00.000Z"
    }
  ],
  "core.settlements": [
    {
      "shop_key": "shopee-open-platform:1001",
      "order_id": "100294",
      "fee_amount": "30000.00",
      "seller_shipping_cost": "8000.00",
      "refund_amount": "0.00",
      "actual_payout": "72000.00",
      "paid_at": "2026-10-29T10:00:00.000Z"
    }
  ]
}
```

## 3. Mart: calculate the measurement

For order 100294: 200,000 sales − 90,000 seller discount − 30,000 fees − 8,000 shipping − 0 refund = 72,000 expected payout. Subtract 130,000 product cost: margin = −58,000 VND. Across the recent offer cohort, 11 of 16 linked orders have complete finances; all 11 lose money, totaling −1,368,000 VND in this Shopee shop.

Run this query against the loaded PostgreSQL database:

```sql
SELECT order_id,gross_sales,seller_discount,fee_amount,seller_shipping_cost,refund_amount,cogs,expected_payout,contribution_margin,financials_complete
FROM mart.order_economics
WHERE shop_key='shopee-open-platform:1001'
  AND order_id='100294';
```

Actual query result:

```json
[
  {
    "order_id": "100294",
    "gross_sales": "200000.00",
    "seller_discount": "90000.00",
    "fee_amount": "30000.00",
    "seller_shipping_cost": "8000.00",
    "refund_amount": "0.00",
    "cogs": "130000.00",
    "expected_payout": "72000.00",
    "contribution_margin": "-58000.00",
    "financials_complete": true
  }
]
```

The order-level example then rolls up to the offer-level mart:

```sql
SELECT shop_key,promotion_id,orders,finance_complete_orders,loss_orders,contribution_margin
FROM mart.promotion_performance
WHERE shop_key='shopee-open-platform:1001'
  AND promotion_id='SAVE90';
```

```json
[
  {
    "shop_key": "shopee-open-platform:1001",
    "promotion_id": "SAVE90",
    "orders": 16,
    "finance_complete_orders": 11,
    "loss_orders": 11,
    "contribution_margin": "-1368000.00"
  }
]
```

## 4. Detection and the input passed to the agent

Trigger: At least 3 negative-margin linked orders and a negative sum of known contribution margins.

Selected fields from the actual `mart.agent_context` packet:

```json
{
  "issue_key": "shopee-open-platform:1001:promotion_loss:SAVE90",
  "shop_key": "shopee-open-platform:1001",
  "merchant_id": "merchant-demo-001",
  "platform": "shopee-open-platform",
  "as_of": "2026-10-30T17:00:00+00:00",
  "issue_type": "promotion_loss",
  "entity_key": "SAVE90",
  "severity": "high",
  "metrics": {
    "margin": -1368000,
    "orders": 16,
    "currency": "VND",
    "attribution": "Associated with promotion; causality unproven",
    "loss_orders": 11,
    "seller_discount": 1800000,
    "finance_complete_orders": 11
  },
  "decision_mode": "suggest_only"
}
```

The complete packet, including windows and evidence, is available in `cases.json` and `mart.json`. The planner uses these facts to classify the problem and request missing information.

## 5. Plan → seller chooses → execute

The following are illustrative planning options. The data pipeline has not executed them. Current settings, target IDs, seller approval and connector results must be supplied by the next component.

| Option | Expected purpose / required input | Cost and risk | Reversibility |
|---|---|---|---|
| Pause the offer after checking current rules | Stop new exposure while investigating; requires live voucher ID and enabled state | Sales may fall; already placed orders are unaffected by the proposed pause | Re-enable only if the platform supports it and previous rules were saved |
| Reduce the seller-funded discount for future orders | Improve projected margin; requires current discount rules and expected fees | Conversion may fall; refunds and fees can still create losses | Restore earlier rules if the API permits the change |

After the seller chooses an option in Telegram, store the approval under this packet’s `issue_key`, fetch the latest target state, execute idempotently, and retain before/after state and rollback parameters where supported. No numeric impact or success is invented here.

## 6. Verify with new data

Collect newly settled orders after the approved change. Compare margin per eligible order, total margin and sales volume with comparable product mix. Example target: nonnegative contribution margin on at least 20 finance-complete new orders.

**What to collect next:** Compare settled contribution margin after the action using comparable SKU mix and enough orders.

The frozen fixture contains no post-action success data. Re-querying it proves reproducibility, not action effectiveness.

**Interpretation limits:** The example changes both discount and fee rate. Association does not prove the voucher alone caused the loss. Margin excludes advertising, overhead and tax; unknown financials are not zero.

Full source → core → mart samples for each platform: [`cases.json`](../cases.json), find `issue_type = "promotion_loss"`. Boundary behavior and unsupported data are explained in the [controls guide](controls.md).
