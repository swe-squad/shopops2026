# How did each shop perform today?

[Back to index](../README.md)

Use `mart.shop_daily` to build a daily seller digest or agency dashboard. This is a reporting use case and does not automatically create an issue.

## 1. Source data

Two actual Shopee order excerpts for October 30 show a completed purchase and a cancellation. The explicit supplement adds costs, order discounts and settlement data. Full-day totals below include all 24 orders, not only these two examples.

```json
{
  "native_orders": [
    {
      "currency": "VND",
      "order_sn": "100312",
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
      "create_time": 1793322000,
      "update_time": 1793347200,
      "order_status": "COMPLETED"
    },
    {
      "currency": "VND",
      "order_sn": "100330",
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
      "create_time": 1793343600,
      "update_time": 1793368800,
      "order_status": "CANCELLED"
    }
  ],
  "demo_supplement": {
    "products": [
      {
        "sku": "SHIRT-M",
        "name": "Áo thun cotton size M",
        "unit_cost": 130000,
        "cost_basis": "seller_supplied_demo"
      }
    ],
    "order_enrichment": [
      {
        "order_id": "100312",
        "promotion_id": "SAVE90",
        "seller_discount": 180000,
        "platform_discount": 10000
      },
      {
        "order_id": "100330",
        "promotion_id": "SAVE90",
        "seller_discount": 90000,
        "platform_discount": 5000
      }
    ],
    "settlements": [
      {
        "paid_at": "2026-10-30T15:00:00+07:00",
        "order_id": "100312",
        "fee_amount": 60000,
        "actual_payout": -58000,
        "refund_amount": 210000,
        "seller_shipping_cost": 8000
      }
    ]
  }
}
```

## 2. General core

```json
{
  "core.products": [
    {
      "shop_key": "shopee-open-platform:1001",
      "sku": "SHIRT-M",
      "unit_cost": "130000.00",
      "cost_basis": "seller_supplied_demo"
    }
  ],
  "core.orders": [
    {
      "shop_key": "shopee-open-platform:1001",
      "order_id": "100312",
      "ordered_at": "2026-10-30T01:00:00.000Z",
      "status": "completed",
      "seller_discount": "180000.00",
      "platform_discount": "10000.00",
      "promotion_id": "SAVE90"
    },
    {
      "shop_key": "shopee-open-platform:1001",
      "order_id": "100330",
      "ordered_at": "2026-10-30T07:00:00.000Z",
      "status": "cancelled",
      "seller_discount": "90000.00",
      "platform_discount": "5000.00",
      "promotion_id": "SAVE90"
    }
  ],
  "core.order_items": [
    {
      "shop_key": "shopee-open-platform:1001",
      "order_id": "100312",
      "line_id": "100:200",
      "sku": "SHIRT-M",
      "quantity": 2,
      "unit_price": "200000.00",
      "status": "completed"
    },
    {
      "shop_key": "shopee-open-platform:1001",
      "order_id": "100330",
      "line_id": "100:200",
      "sku": "SHIRT-M",
      "quantity": 1,
      "unit_price": "200000.00",
      "status": "cancelled"
    }
  ],
  "core.settlements": [
    {
      "shop_key": "shopee-open-platform:1001",
      "order_id": "100312",
      "fee_amount": "60000.00",
      "seller_shipping_cost": "8000.00",
      "refund_amount": "210000.00",
      "actual_payout": "-58000.00",
      "paid_at": "2026-10-30T08:00:00.000Z"
    }
  ]
}
```

Product unit costs are joined by shop + SKU when calculating `mart.order_economics`. A cancelled order has no settled margin here. The daily view groups those per-order facts by shop, local order date and currency.

## 3. Mart query and actual result

```sql
SELECT shop_key,business_date::text,currency,orders,cancelled_orders,unmapped_or_mixed_orders,finance_complete_orders,contribution_margin,fulfilled_gross_sales
FROM mart.shop_daily
WHERE business_date='2026-10-30'
ORDER BY shop_key;
```

```json
[
  {
    "shop_key": "lazada:1001",
    "business_date": "2026-10-30",
    "currency": "VND",
    "orders": 24,
    "cancelled_orders": 6,
    "unmapped_or_mixed_orders": 0,
    "finance_complete_orders": 14,
    "contribution_margin": "-622000.00",
    "fulfilled_gross_sales": "2800000.00"
  },
  {
    "shop_key": "shopee-open-platform:1001",
    "business_date": "2026-10-30",
    "currency": "VND",
    "orders": 24,
    "cancelled_orders": 6,
    "unmapped_or_mixed_orders": 0,
    "finance_complete_orders": 14,
    "contribution_margin": "-622000.00",
    "fulfilled_gross_sales": "2800000.00"
  },
  {
    "shop_key": "shopee-open-platform:1002",
    "business_date": "2026-10-30",
    "currency": "VND",
    "orders": 24,
    "cancelled_orders": 1,
    "unmapped_or_mixed_orders": 0,
    "finance_complete_orders": 23,
    "contribution_margin": "1536000.00",
    "fulfilled_gross_sales": "4900000.00"
  },
  {
    "shop_key": "shopify:1001",
    "business_date": "2026-10-30",
    "currency": "VND",
    "orders": 24,
    "cancelled_orders": 6,
    "unmapped_or_mixed_orders": 0,
    "finance_complete_orders": 14,
    "contribution_margin": "-652000.00",
    "fulfilled_gross_sales": "2800000.00"
  }
]
```

For the affected Shopee shop, October 30 has 24 orders, 6 cancellations, 14 finance-complete orders and −622,000 VND summed known contribution margin. Four orders are still open. `contribution_margin` covers eligible orders only; `fulfilled_gross_sales` is before the separately recorded order discounts. The date is the local order date, not the payout date.

## 4. Input to the next component

Pass the four daily rows to a reporting agent as `daily_shop_summary`, together with `as_of`, currency and completeness counts. This is an illustrative report envelope, not a stored `mart.agent_context` issue packet:

```json
{
  "report_type": "daily_shop_summary",
  "as_of": "2026-10-30T17:00:00.000Z",
  "business_date": "2026-10-30",
  "rows": [
    {
      "shop_key": "lazada:1001",
      "business_date": "2026-10-30",
      "currency": "VND",
      "orders": 24,
      "cancelled_orders": 6,
      "unmapped_or_mixed_orders": 0,
      "finance_complete_orders": 14,
      "contribution_margin": "-622000.00",
      "fulfilled_gross_sales": "2800000.00"
    },
    {
      "shop_key": "shopee-open-platform:1001",
      "business_date": "2026-10-30",
      "currency": "VND",
      "orders": 24,
      "cancelled_orders": 6,
      "unmapped_or_mixed_orders": 0,
      "finance_complete_orders": 14,
      "contribution_margin": "-622000.00",
      "fulfilled_gross_sales": "2800000.00"
    },
    {
      "shop_key": "shopee-open-platform:1002",
      "business_date": "2026-10-30",
      "currency": "VND",
      "orders": 24,
      "cancelled_orders": 1,
      "unmapped_or_mixed_orders": 0,
      "finance_complete_orders": 23,
      "contribution_margin": "1536000.00",
      "fulfilled_gross_sales": "4900000.00"
    },
    {
      "shop_key": "shopify:1001",
      "business_date": "2026-10-30",
      "currency": "VND",
      "orders": 24,
      "cancelled_orders": 6,
      "unmapped_or_mixed_orders": 0,
      "finance_complete_orders": 14,
      "contribution_margin": "-652000.00",
      "fulfilled_gross_sales": "2800000.00"
    }
  ]
}
```

## 5. Seller use

The seller can open the voucher-loss case to investigate margin or the cancellation case to inspect operational changes. Do not infer that all 24 orders were measured for profit or that a low daily total proves one specific cause.

## 6. Verify later

Collect new orders and settlements, rebuild the daily view and compare equivalent local days with finance completeness shown. A changing subtotal can reflect later settlement availability. There is no seller-approved action or observed improvement in this reporting example.
