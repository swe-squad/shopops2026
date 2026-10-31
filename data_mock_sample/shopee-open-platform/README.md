# Shopee connector fixture

`raw/1001_orders.json` and `raw/1002_orders.json` wrap a provisional `get_order_detail`-shaped payload. The raw wrapper records `source_kind = provisional_api_subset`: Shopee's official reference returned HTTP 403 during research. This is a proposed mock contract, not a verified full response.

```text
payload.response.order_list[]
  order_sn: string
  create_time, update_time: Unix seconds
  currency: string
  order_status: string
  item_list[]:
    item_id, model_id: integer
    model_sku: string
    model_quantity_purchased: integer
    model_original_price, model_discounted_price: number (major currency units)
```

Order line identity is `item_id:model_id` within an order. This demo treats model discounted price as the unit price before the separately supplied order voucher. Validate actual price semantics before replacing the mock source.

`raw/*_supplement.json` is **our own** merchant/demo contract. It contains catalog/COGS, reviews, returns, inventory, promotion definitions, settlement summaries, shipping deadlines, penalties and order discount enrichment. None of those payloads claim to be Shopee API responses.

`core/*.jsonl` contains normalized table rows for both shops, preserving shop-scoped IDs. Shop `1001` has incidents; `1002` is the healthy control. Mapping logic lives in [normalize.py](../scripts/normalize.py); table types are in [001_schema.sql](../sql/001_schema.sql). Sources: [S1–S2](../SOURCES.md).
