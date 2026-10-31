# Lazada connector fixture

The order integration guide documents two important differences: order IDs are scoped to a shop, and each purchased unit has its own item ID/status. The adapter preserves both. The full response schema was not extractable from the interactive reference, so the fixture is a minimal API-inspired subset requiring live contract verification.

```text
raw/1001_orders.json → payload.data.orders[]
  order_id: integer
  created_at, updated_at: "YYYY-MM-DD HH:MM:SS +0700"
  statuses: string[]
  price, voucher_seller, voucher_platform: decimal strings

raw/1001_order_items.json → payload.responses[] → data[]
  order_id, order_item_id: integer
  sku, status, currency: string
  item_price: decimal string
```

`responses` is a local bundle of per-order `/order/items/get` responses, not an API response field. A quantity-two purchase becomes two unit rows. Orders with conflicting item statuses normalize to `mixed`; their financial allocation is not inferred.

`raw/1001_supplement.json` holds the local demo contract for the other entities. Lazada review APIs exist, but exact review response fields were not verified; the review supplement does not pretend to implement them. Account-health records are also demo events, not a verified Lazada penalty-points schema.

See [core/*.jsonl](core/), [the shared schema](../sql/001_schema.sql), [adapter logic](../scripts/normalize.py), and [sources L1–L6](../SOURCES.md).
