# Will the popular shirt sell out before the seller replenishes it?

[Back to use-case index](../README.md) · [Complete field reference](../reference.md)

Use this case to answer: **Will the popular shirt sell out before the seller replenishes it?**

Marts used: `mart.inventory_risk`, `mart.issue_candidates`, `mart.agent_context`. The main calculation is shown below; `issue_candidates` applies the trigger and `agent_context` packages it for the planner.

All measured values below come from the fixed fixture clock, **2026-10-31 00:00 Vietnam time**. Recent window is October 29–30; baseline is October 17–28. The raw/core snippets are representative records; the SQL aggregates use the full source population.

## 1. Source data: what the connector received

The main example uses Shopee shop `1001`. Native order fields are provisional; operational records such as reviews, finance, inventory and health are explicitly labeled demo supplements.

```json
{
  "product": {
    "sku": "SHIRT-M",
    "name": "Áo thun cotton size M",
    "unit_cost": 130000,
    "cost_basis": "seller_supplied_demo"
  },
  "stock_observations": [
    {
      "sku": "SHIRT-M",
      "available": 250,
      "location_id": "VN-HCM-1",
      "observed_at": "2026-10-28T23:00:00+07:00"
    },
    {
      "sku": "SHIRT-M",
      "available": 2,
      "location_id": "VN-HCM-1",
      "observed_at": "2026-10-30T23:00:00+07:00"
    }
  ],
  "demand_order": {
    "currency": "VND",
    "order_sn": "100168",
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
    "create_time": 1792803600,
    "update_time": 1792828800,
    "order_status": "COMPLETED"
  },
  "order_enrichment": [
    {
      "order_id": "100168",
      "promotion_id": null,
      "seller_discount": 20000,
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
  "product": {
    "sku": "SHIRT-M",
    "name": "Áo thun cotton size M",
    "unit_cost": 130000,
    "cost_basis": "seller_supplied_demo"
  },
  "stock_observations": [
    {
      "sku": "SHIRT-M",
      "available": 250,
      "location_id": "VN-HCM-1",
      "observed_at": "2026-10-28T23:00:00+07:00"
    },
    {
      "sku": "SHIRT-M",
      "available": 2,
      "location_id": "VN-HCM-1",
      "observed_at": "2026-10-30T23:00:00+07:00"
    }
  ],
  "demand_order": {
    "price": "400000",
    "order_id": 100168,
    "statuses": [
      "delivered"
    ],
    "created_at": "2026-10-24 08:00:00 +0700",
    "updated_at": "2026-10-24 15:00:00 +0700",
    "voucher_seller": "20000",
    "voucher_platform": "10000"
  },
  "order_enrichment": [
    {
      "order_id": "100168",
      "promotion_id": null,
      "seller_discount": 20000,
      "platform_discount": 10000
    }
  ],
  "order_items": [
    {
      "sku": "SHIRT-M",
      "status": "delivered",
      "currency": "VND",
      "order_id": 100168,
      "item_price": "200000",
      "order_item_id": 1001680
    },
    {
      "sku": "SHIRT-M",
      "status": "delivered",
      "currency": "VND",
      "order_id": 100168,
      "item_price": "200000",
      "order_item_id": 1001681
    }
  ]
}
```

### shopify

```json
{
  "product": {
    "sku": "SHIRT-M",
    "name": "Áo thun cotton size M",
    "unit_cost": 130000,
    "cost_basis": "seller_supplied_demo"
  },
  "stock_observations": [
    {
      "sku": "SHIRT-M",
      "available": 250,
      "location_id": "VN-HCM-1",
      "observed_at": "2026-10-28T23:00:00+07:00"
    },
    {
      "sku": "SHIRT-M",
      "available": 2,
      "location_id": "VN-HCM-1",
      "observed_at": "2026-10-30T23:00:00+07:00"
    }
  ],
  "demand_order": {
    "id": "gid://shopify/Order/100168",
    "createdAt": "2026-10-24T08:00:00+07:00",
    "lineItems": {
      "nodes": [
        {
          "id": "gid://shopify/LineItem/1001680",
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
    "updatedAt": "2026-10-24T15:00:00+07:00",
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
  "order_enrichment": [
    {
      "order_id": "100168",
      "promotion_id": null,
      "seller_discount": 20000,
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
  "core.inventory": [
    {
      "shop_key": "shopee-open-platform:1001",
      "sku": "SHIRT-M",
      "location_id": "VN-HCM-1",
      "observed_at": "2026-10-30T16:00:00.000Z",
      "available": 2
    },
    {
      "shop_key": "shopee-open-platform:1001",
      "sku": "SHIRT-M",
      "location_id": "VN-HCM-1",
      "observed_at": "2026-10-28T16:00:00.000Z",
      "available": 250
    }
  ],
  "core.order_items": [
    {
      "shop_key": "shopee-open-platform:1001",
      "order_id": "100168",
      "line_id": "100:200",
      "sku": "SHIRT-M",
      "quantity": 2,
      "unit_price": "200000.00",
      "status": "completed"
    }
  ],
  "core.orders": [
    {
      "shop_key": "shopee-open-platform:1001",
      "order_id": "100168",
      "ordered_at": "2026-10-24T01:00:00.000Z",
      "status": "completed",
      "seller_discount": "20000.00",
      "platform_discount": "10000.00",
      "promotion_id": null
    }
  ]
}
```

## 3. Mart: calculate the measurement

The latest sellable stock is 2 shirts. Recognized noncancelled demand is 64 units over 7 days: 64 / 7 ≈ 9.1429 per day. Coverage = 2 / (64 / 7) = 0.21875 days, about 5.25 hours under this simple average-demand assumption.

Run this query against the loaded PostgreSQL database:

```sql
SELECT shop_key,sku,available,oldest_location_observation,daily_units,days_of_cover
FROM mart.inventory_risk
WHERE shop_key='shopee-open-platform:1001'
  AND sku='SHIRT-M';
```

Actual query result:

```json
[
  {
    "shop_key": "shopee-open-platform:1001",
    "sku": "SHIRT-M",
    "available": 2,
    "oldest_location_observation": "2026-10-30T16:00:00.000Z",
    "daily_units": "9.1428571428571429",
    "days_of_cover": "0.21874999999999999897"
  }
]
```

## 4. Detection and the input passed to the agent

Trigger: Coverage below 2 days, average demand at least 1 unit/day, and selected stock observations no more than 24 hours old.

Selected fields from the actual `mart.agent_context` packet:

```json
{
  "issue_key": "shopee-open-platform:1001:low_stock:SHIRT-M",
  "shop_key": "shopee-open-platform:1001",
  "platform": "shopee-open-platform",
  "as_of": "2026-10-30T17:00:00+00:00",
  "issue_type": "low_stock",
  "entity_key": "SHIRT-M",
  "severity": "high",
  "metrics": {
    "available": 2,
    "daily_units": 9.142857142857142,
    "observed_at": "2026-10-30T16:00:00+00:00",
    "days_of_cover": 0.21875
  },
  "decision_mode": "suggest_only"
}
```

The complete packet, including windows and evidence, is available in `cases.json` and `mart.json`. The planner uses these facts to classify the problem and request missing information.

## 5. Plan → seller chooses → execute

The following are illustrative planning options. The data pipeline has not executed them. Current settings, target IDs, seller approval and connector results must be supplied by the next component.

| Option | Expected purpose / required input | Cost and risk | Reversibility |
|---|---|---|---|
| Confirm stock and request supplier lead time/quote | Validate urgency and estimate a replenishment quantity | Staff time; unit cost is known but lead time and delivered purchase cost are missing | Investigation can be stopped; a purchase commitment may not be reversible |
| After approval, arrange replenishment or adjust availability | Reduce stockout exposure or prevent overselling | Purchase cash requirement or lower sales; requires confirmed physical stock | Availability edits may be reverted; purchasing needs a separate rollback policy |

After the seller chooses an option in Telegram, store the approval under this packet’s `issue_key`, fetch the latest target state, execute idempotently, and retain before/after state and rollback parameters where supported. No numeric impact or success is invented here.

## 6. Verify with new data

Read a fresh post-replenishment stock snapshot. Recalculate days of cover with current demand. Example criterion: at least 2 days of cover, with all location snapshots less than 24 hours old.

**What to collect next:** Collect a fresh stock snapshot after replenishment and recalculate coverage.

The frozen fixture contains no post-action success data. Re-querying it proves reproducibility, not action effectiveness.

**Interpretation limits:** Coverage is a trailing average, not a forecast. Do not simply increase marketplace stock without physical inventory. Unknown or stale stock suppresses the alert rather than becoming zero.

Full source → core → mart samples for each platform: [`cases.json`](../cases.json), find `issue_type = "low_stock"`. Boundary behavior and unsupported data are explained in the [controls guide](controls.md).
