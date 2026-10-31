# Worked example: three raw formats → one core → one mart

This walkthrough compares actual Shopee, Lazada and Shopify fixture records through the shared adapters and PostgreSQL views, using two purchases per platform. For seller problems, start with the [use-case index](README.md). Every dictionary example and boundary output is preserved in the [complete reference](reference.md).

| Purchase | Source ID suffix | Items | Seller discount | Purpose |
|---|---|---|---:|---|
| Baseline | `100000` | Two shirts at 200,000 VND each | 20,000 VND total | Show different item shapes producing the same totals. |
| Incident | `100294` | One shirt at 200,000 VND | 90,000 VND | Show the same shared margin calculation identifying a loss. |

These are separate synthetic purchases in separate platform shops. Similar IDs/amounts are intentional; they are not records to deduplicate across platforms.

The generated artifacts are:

- [All Shopee raw fixture batches](raw/shopee-open-platform.json)
- [All Lazada raw fixture batches](raw/lazada.json)
- [All Shopify raw fixture batches](raw/shopify.json)
- [All 11 combined core tables](core.json)
- [All eight mart views, settings, and 29 agent packets](mart.json)
- [All nine business cases traced through every supported platform](cases.json)
- [Missing-data and boundary-case results](edge-cases.json)
- [Illustrative future agent records from the dictionary](future-agent-examples.json)
- [Dataset manifest and validation-report examples](metadata.json)
- [Field and case coverage results](coverage.json)

Shopee remains a provisional API subset. Other operational sources here are explicit demo supplements. Raw exports preserve the complete existing synthetic fixture batches and original document IDs. The selected snippets below are explanatory excerpts. API confidence levels are preserved in each raw document.

## 1. Different raw inputs

The snippets below show the baseline purchase. Selected fields are shown; the linked raw files also contain envelopes, updates, supplements, and the incident order.

### Shopee: nested order items and numeric prices

From `payload.response.order_list[]`:

```json
{
  "order_sn": "100000",
  "create_time": 1792198800,
  "currency": "VND",
  "order_status": "COMPLETED",
  "item_list": [
    {
      "item_id": 100,
      "model_id": 200,
      "model_sku": "SHIRT-M",
      "model_quantity_purchased": 2,
      "model_discounted_price": 200000
    }
  ]
}
```

The adapter converts epoch seconds to a timestamp, maps the order status, and uses `item_id:model_id` as the line ID. This order subset does not contain the seller-funded voucher amount; that comes from the explicitly labeled supplement.

### Lazada: order header plus individual unit records

From the order header in `payload.data.orders[]`:

```json
{
  "order_id": 100000,
  "created_at": "2026-10-17 08:00:00 +0700",
  "statuses": ["delivered"],
  "price": "400000",
  "voucher_seller": "20000",
  "voucher_platform": "10000"
}
```

From the associated item response:

```json
{
  "code": "0",
  "data": [
    {
      "order_id": 100000,
      "order_item_id": 1000000,
      "sku": "SHIRT-M",
      "item_price": "200000",
      "status": "delivered",
      "currency": "VND"
    },
    {
      "order_id": 100000,
      "order_item_id": 1000001,
      "sku": "SHIRT-M",
      "item_price": "200000",
      "status": "delivered",
      "currency": "VND"
    }
  ]
}
```

Each unit becomes one core line with quantity one. The adapter derives the order state from the item states. Both are delivered here; conflicting states would produce `mixed` instead.

### Shopify: GraphQL connections, global IDs and MoneyBag objects

From `payload.data.orders.nodes[]`:

```json
{
  "id": "gid://shopify/Order/100000",
  "createdAt": "2026-10-17T08:00:00+07:00",
  "currencyCode": "VND",
  "cancelledAt": null,
  "displayFulfillmentStatus": "FULFILLED",
  "totalDiscountsSet": {
    "shopMoney": {"amount": "20000", "currencyCode": "VND"}
  },
  "lineItems": {
    "nodes": [
      {
        "id": "gid://shopify/LineItem/1000000",
        "sku": "SHIRT-M",
        "quantity": 2,
        "originalUnitPriceSet": {
          "shopMoney": {"amount": "200000", "currencyCode": "VND"}
        }
      }
    ]
  }
}
```

The adapter retains global IDs, extracts the shop-currency money, and maps `FULFILLED` to `shipped`. Fulfillment is not treated as proof of delivery. Discounts are merchant-funded by fixture assumption, and no platform subsidy is modeled for Shopify.

## 2. Supply the extra facts needed for margin

None of those order snippets alone establishes profit. The fixture supplement provides product cost and financial outcomes. For the baseline order, every shop has the following values:

| Source record | Field | Value |
|---|---|---|
| Product | `sku` | `SHIRT-M` |
| Product | `unit_cost` | 130,000 VND per shirt |
| Product | `cost_basis` | `seller_supplied_demo` |
| Settlement | `order_id` | `100000` before Shopify ID normalization |
| Settlement | `fee_amount` | 20,000 VND |
| Settlement | `seller_shipping_cost` | 8,000 VND |
| Settlement | `refund_amount` | 0 VND |
| Settlement | `actual_payout` | 352,000 VND |
| Settlement | `paid_at` | `2026-10-17T15:00:00+07:00` |

The order enrichment supplies Shopee's 20,000 VND seller discount. Lazada reads it from `voucher_seller`; Shopify reads it from `totalDiscountsSet.shopMoney.amount`. Shopee/Lazada each have a 10,000 VND platform-funded discount; Shopify has zero. Under the demo reimbursement assumption, these platform discounts do not reduce seller proceeds.

The raw excerpt files label these records `demo_supplement`; they are not presented as native finance API responses.

## 3. Map each source into the general core

These transformations are implemented in [normalize.py](../../scripts/normalize.py).

| Shared target | Shopee input / rule | Lazada input / rule | Shopify input / rule |
|---|---|---|---|
| `shop_key` | Platform + source shop ID | Same convention | Same convention |
| `order_id` | `order_sn` | Convert numeric `order_id` to text | Preserve full `id` |
| `ordered_at` | Decode `create_time` Unix seconds | Parse `created_at` including offset | Parse `createdAt` |
| `currency` | `currency` | Matching currency from unit records | `currencyCode` |
| `status` | `COMPLETED` → `completed` | All units `delivered` → `completed` | `FULFILLED` → `shipped` unless cancelled |
| `seller_discount` | Supplemental enrichment | `voucher_seller` | `totalDiscountsSet.shopMoney.amount` |
| `line_id` | `item_id:model_id` | Text `order_item_id` | Full line global ID |
| `sku` | `model_sku` | `sku` | `sku` |
| `quantity` | `model_quantity_purchased` | One for each unit record | `quantity` |
| `unit_price` | `model_discounted_price` | `item_price` | `originalUnitPriceSet.shopMoney.amount` |

The baseline rows in `core.orders` become:

| `shop_key` | `order_id` | `ordered_at` shown in UTC | `status` | `seller_discount` | `platform_discount` |
|---|---|---|---|---:|---:|
| `shopee-open-platform:1001` | `100000` | `2026-10-17 01:00:00Z` | `completed` | 20,000 | 10,000 |
| `lazada:1001` | `100000` | `2026-10-17 01:00:00Z` | `completed` | 20,000 | 10,000 |
| `shopify:1001` | `gid://shopify/Order/100000` | `2026-10-17 01:00:00Z` | `shipped` | 20,000 | 0 |

Their `core.order_items` rows become:

| `shop_key` | `line_id` | `sku` | `quantity` | `unit_price` |
|---|---|---|---:|---:|
| `shopee-open-platform:1001` | `100:200` | `SHIRT-M` | 2 | 200,000 |
| `lazada:1001` | `1000000` | `SHIRT-M` | 1 | 200,000 |
| `lazada:1001` | `1000001` | `SHIRT-M` | 1 | 200,000 |
| `shopify:1001` | `gid://shopify/LineItem/1000000` | `SHIRT-M` | 2 | 200,000 |

The columns and business meaning are shared, while source identity and line granularity remain intact. The general mart can sum quantities without needing to know which source used one line versus two.

`core.products` supplies one `SHIRT-M` row per shop with unit cost 130,000. `core.settlements` supplies one financial summary per order. Every record retains its raw `source_document_id`. The exported [core.json](core.json) contains every row and field from all 11 core tables, including reviews, returns, inventory, fulfillment and account health. The tables above select the baseline purchase to keep the mapping readable.

## 4. Use one financial mart for every platform

The actual calculation is implemented once in [mart/002_views.sql](../../mart/002_views.sql). There is no separate Shopee margin formula or Lazada margin formula after normalization.

```text
gross_sales         = sum(quantity × unit_price)
cogs                = sum(quantity × unit_cost)
expected_payout     = gross_sales − seller_discount − fees − shipping − refunds
contribution_margin = expected_payout − cogs
payout_variance     = actual_payout − expected_payout
```

The following query runs against the existing PostgreSQL database:

```sql
SELECT shop_key, order_id, units, gross_sales, seller_discount,
       fee_amount, seller_shipping_cost, refund_amount, cogs,
       expected_payout, contribution_margin, payout_variance
FROM mart.order_economics
WHERE shop_key IN ('shopee-open-platform:1001', 'lazada:1001', 'shopify:1001')
  AND order_id IN ('100000', '100294',
                  'gid://shopify/Order/100000', 'gid://shopify/Order/100294')
ORDER BY shop_key, order_id;
```

The resulting selected financial rows are:

| Shop | Order ID suffix | Units | Sales | Seller discount | Fees | Shipping | Refund | Product cost | Expected payout | Margin |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Shopee `1001` | `100000` | 2 | 400,000 | 20,000 | 20,000 | 8,000 | 0 | 260,000 | 352,000 | **92,000** |
| Lazada `1001` | `100000` | 2 | 400,000 | 20,000 | 20,000 | 8,000 | 0 | 260,000 | 352,000 | **92,000** |
| Shopify `1001` | `100000` | 2 | 400,000 | 20,000 | 20,000 | 8,000 | 0 | 260,000 | 352,000 | **92,000** |
| Shopee `1001` | `100294` | 1 | 200,000 | 90,000 | 30,000 | 8,000 | 0 | 130,000 | 72,000 | **−58,000** |
| Lazada `1001` | `100294` | 1 | 200,000 | 90,000 | 30,000 | 8,000 | 0 | 130,000 | 72,000 | **−58,000** |
| Shopify `1001` | `100294` | 1 | 200,000 | 90,000 | 30,000 | 8,000 | 0 | 130,000 | 72,000 | **−58,000** |

Amounts are VND. All six selected rows have complete modeled financials, and their actual payouts equal expected payouts, so payout variance is zero. A zero payout discrepancy does not imply a profitable order: the promotional orders settle correctly but lose money after product cost.

The incident example has both a larger seller discount and a higher fee rate. It demonstrates a measured loss, not proof that the voucher alone caused it.

## 5. Aggregate the full recent window into an agent issue

One losing sample order is not enough to satisfy the current promotion alert's minimum of three loss orders. The export therefore queries the **full existing dataset** for promotion-level metrics and agent packets, rather than claiming they came from only the six displayed orders.

```sql
SELECT shop_key, promotion_id, orders, finance_complete_orders,
       loss_orders, contribution_margin
FROM mart.promotion_performance
WHERE promotion_id = 'SAVE90'
ORDER BY shop_key;
```

| Shop | Linked recent orders | Finance-complete orders | Loss orders | Known contribution margin |
|---|---:|---:|---:|---:|
| Shopee `1001` | 16 | 11 | 11 | −1,368,000 VND |
| Lazada `1001` | 16 | 11 | 11 | −1,368,000 VND |
| Shopify `1001` | 16 | 11 | 11 | −1,398,000 VND |

Totals need not match across platforms. Shopify's fixture has no platform subsidy, and its refunded orders consequently contain different refund amounts. Core normalization preserves that difference.

The shared detector creates a `promotion_loss` candidate for each shop. A selected-field excerpt of the Shopee agent packet is:

```json
{
  "shop_key": "shopee-open-platform:1001",
  "issue_key": "shopee-open-platform:1001:promotion_loss:SAVE90",
  "issue_type": "promotion_loss",
  "entity_key": "SAVE90",
  "currency": "VND",
  "severity": "high",
  "metrics": {
    "orders": 16,
    "finance_complete_orders": 11,
    "loss_orders": 11,
    "margin": -1368000,
    "attribution": "Associated with promotion; causality unproven"
  },
  "decision_mode": "suggest_only"
}
```

The agent can now use the same planning workflow for all three shops: investigate the discount and fee changes, propose options, and define a margin metric for verification. It still needs current voucher configuration and seller approval before execution. Full packets, including evidence and windows, are in [mart.json](mart.json).

## 6. Rebuild the example

From the repository root, after installing the existing Node dependency:

```powershell
npm.cmd run example
```

On macOS/Linux use `npm run example`. This command re-normalizes the existing raw fixtures, loads them into embedded PostgreSQL, queries the same mart SQL, exports the walkthrough files, and checks the selected quantities, margins and payout variances. It does not regenerate or overwrite hand-edited raw source fixtures. If raw fixtures are absent, first run `python mock-data/scripts/generate.py`.

The export uses [export-walkthrough.mjs](../../scripts/export-walkthrough.mjs), [complete-samples.mjs](../../scripts/complete-samples.mjs), and [use-case-guides.mjs](../../scripts/use-case-guides.mjs). It checks the six introductory financial rows, exports the full dataset and all 29 packets, checks database field coverage, and regenerates the [complete reference](reference.md) and [use-case guides](README.md). Boundary scenarios run in transactions rolled back before export completion. Use the existing seed loader to populate a PostgreSQL database.
