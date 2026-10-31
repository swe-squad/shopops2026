# Which open orders need dispatch attention now?

[Back to use-case index](../README.md) · [Complete field reference](../reference.md)

Use this case to answer: **Which open orders need dispatch attention now?**

Marts used: `mart.issue_candidates`, `mart.agent_context`. The main calculation is shown below; `issue_candidates` applies the trigger and `agent_context` packages it for the planner.

All measured values below come from the fixed fixture clock, **2026-10-31 00:00 Vietnam time**. Recent window is October 29–30; baseline is October 17–28. The raw/core snippets are representative records; the SQL aggregates use the full source population.

These are administrative fixture queries. For a logged-in user, join `access.user_shop_access` and bind the verified session user ID as shown in the [access guide](../../../access/README.md).

## 1. Source data: what the connector received

The main example uses Shopee shop `1001`. Native order fields are provisional; operational records such as reviews, finance, inventory and health are explicitly labeled demo supplements.

```json
{
  "order": {
    "currency": "VND",
    "order_sn": "100326",
    "item_list": [
      {
        "item_id": 102,
        "model_id": 202,
        "model_sku": "TOTE",
        "model_original_price": 250000,
        "model_discounted_price": 250000,
        "model_quantity_purchased": 2
      }
    ],
    "create_time": 1793338800,
    "update_time": 1793364000,
    "order_status": "READY_TO_SHIP"
  },
  "fulfillment": {
    "ship_by": "2026-10-30T15:40:00+07:00",
    "order_id": "100326",
    "shipped_at": null,
    "deadline_basis": "demo_policy_not_marketplace_SLA"
  },
  "order_enrichment": [
    {
      "order_id": "100326",
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
  "order": {
    "price": "500000",
    "order_id": 100326,
    "statuses": [
      "pending"
    ],
    "created_at": "2026-10-30 12:40:00 +0700",
    "updated_at": "2026-10-30 19:40:00 +0700",
    "voucher_seller": "20000",
    "voucher_platform": "10000"
  },
  "fulfillment": {
    "ship_by": "2026-10-30T15:40:00+07:00",
    "order_id": "100326",
    "shipped_at": null,
    "deadline_basis": "demo_policy_not_marketplace_SLA"
  },
  "order_enrichment": [
    {
      "order_id": "100326",
      "promotion_id": null,
      "seller_discount": 20000,
      "platform_discount": 10000
    }
  ],
  "order_items": [
    {
      "sku": "TOTE",
      "status": "pending",
      "currency": "VND",
      "order_id": 100326,
      "item_price": "250000",
      "order_item_id": 1003260
    },
    {
      "sku": "TOTE",
      "status": "pending",
      "currency": "VND",
      "order_id": 100326,
      "item_price": "250000",
      "order_item_id": 1003261
    }
  ]
}
```

### shopify

```json
{
  "order": {
    "id": "gid://shopify/Order/100326",
    "createdAt": "2026-10-30T12:40:00+07:00",
    "lineItems": {
      "nodes": [
        {
          "id": "gid://shopify/LineItem/1003260",
          "sku": "TOTE",
          "quantity": 2,
          "originalUnitPriceSet": {
            "shopMoney": {
              "amount": "250000",
              "currencyCode": "VND"
            }
          }
        }
      ]
    },
    "updatedAt": "2026-10-30T19:40:00+07:00",
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
    "displayFulfillmentStatus": "UNFULFILLED"
  },
  "fulfillment": {
    "ship_by": "2026-10-30T15:40:00+07:00",
    "order_id": "100326",
    "shipped_at": null,
    "deadline_basis": "demo_policy_not_marketplace_SLA"
  },
  "order_enrichment": [
    {
      "order_id": "100326",
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
  "core.fulfillment": [
    {
      "shop_key": "shopee-open-platform:1001",
      "order_id": "100326",
      "ship_by": "2026-10-30T08:40:00.000Z",
      "shipped_at": null,
      "deadline_basis": "demo_policy_not_marketplace_SLA"
    }
  ],
  "core.orders": [
    {
      "shop_key": "shopee-open-platform:1001",
      "order_id": "100326",
      "ordered_at": "2026-10-30T05:40:00.000Z",
      "status": "open",
      "seller_discount": "20000.00",
      "platform_discount": "10000.00",
      "promotion_id": null
    }
  ]
}
```

## 3. Mart: calculate the measurement

Select open orders with no dispatch timestamp and ship_by before as_of + 6 hours. The fixture has 4 qualifying orders; all 4 are already overdue at the frozen clock. Group them into one shop-level issue.

Run this query against the loaded PostgreSQL database:

```sql
SELECT o.shop_key,o.order_id,o.status,f.ship_by,f.shipped_at,f.deadline_basis
FROM core.orders o JOIN core.fulfillment f USING(shop_key,order_id) CROSS JOIN mart.settings s
WHERE o.shop_key='shopee-open-platform:1001'
  AND o.status='open'
  AND f.shipped_at IS NULL
  AND f.ship_by<s.as_of+interval '6 hours'
ORDER BY o.order_id;
```

Actual query result:

```json
[
  {
    "shop_key": "shopee-open-platform:1001",
    "order_id": "100326",
    "status": "open",
    "ship_by": "2026-10-30T08:40:00.000Z",
    "shipped_at": null,
    "deadline_basis": "demo_policy_not_marketplace_SLA"
  },
  {
    "shop_key": "shopee-open-platform:1001",
    "order_id": "100327",
    "status": "open",
    "ship_by": "2026-10-30T09:00:00.000Z",
    "shipped_at": null,
    "deadline_basis": "demo_policy_not_marketplace_SLA"
  },
  {
    "shop_key": "shopee-open-platform:1001",
    "order_id": "100328",
    "status": "open",
    "ship_by": "2026-10-30T09:20:00.000Z",
    "shipped_at": null,
    "deadline_basis": "demo_policy_not_marketplace_SLA"
  },
  {
    "shop_key": "shopee-open-platform:1001",
    "order_id": "100329",
    "status": "open",
    "ship_by": "2026-10-30T09:40:00.000Z",
    "shipped_at": null,
    "deadline_basis": "demo_policy_not_marketplace_SLA"
  }
]
```

## 4. Detection and the input passed to the agent

Trigger: At least one open, unshipped order due before the next six-hour boundary. Cancelled orders are excluded.

Selected fields from the actual `mart.agent_context` packet:

```json
{
  "issue_key": "shopee-open-platform:1001:shipment_risk:shop",
  "shop_key": "shopee-open-platform:1001",
  "merchant_id": "merchant-demo-001",
  "platform": "shopee-open-platform",
  "as_of": "2026-10-30T17:00:00+00:00",
  "issue_type": "shipment_risk",
  "entity_key": "shop",
  "severity": "high",
  "metrics": {
    "at_risk_orders": 4,
    "overdue_orders": 4
  },
  "decision_mode": "suggest_only"
}
```

The complete packet, including windows and evidence, is available in `cases.json` and `mart.json`. The planner uses these facts to classify the problem and request missing information.

## 5. Plan → seller chooses → execute

The following are illustrative planning options. The data pipeline has not executed them. Current settings, target IDs, seller approval and connector results must be supplied by the next component.

| Option | Expected purpose / required input | Cost and risk | Reversibility |
|---|---|---|---|
| Prioritize packing and confirm carrier handoff availability | Focus staff on the four at-risk orders | Staff/overtime cost unknown; requires actual packing/carrier state | A work assignment can be changed; physical handoff cannot be undone |
| After seller choice, arrange a supported pickup or handoff | Complete dispatch and limit further delay | Carrier availability and fees are unknown until checked | Pickup cancellation depends on the carrier/API |

After the seller chooses an option in Telegram, store the approval under this packet’s `issue_key`, fetch the latest target state, execute idempotently, and retain before/after state and rollback parameters where supported. No numeric impact or success is invented here.

## 6. Verify with new data

Collect genuine dispatch confirmations. Check shipped_at against each original deadline and confirm the open-risk backlog is cleared. Already late orders remain historically late even after dispatch.

**What to collect next:** Collect dispatch confirmations and compare actual dispatch times with order deadlines.

The frozen fixture contains no post-action success data. Re-querying it proves reproducibility, not action effectiveness.

**Interpretation limits:** These are demo dispatch deadlines, not official Shopee SLAs. This case reads core fulfillment directly; no dedicated shipping mart view exists.

Full source → core → mart samples for each platform: [`cases.json`](../cases.json), find `issue_type = "shipment_risk"`. Boundary behavior and unsupported data are explained in the [controls guide](controls.md).
