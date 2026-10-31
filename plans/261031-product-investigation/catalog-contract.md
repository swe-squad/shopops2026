# Catalog read contract

All routes below use the existing workspace bearer authentication. Backend-only identity mapping uses the source user's current access grants. Browser-supplied identity headers cannot select a principal. Multi-user registration/identity integration remains the AI engineer's boundary.

- GET `/api/operations/catalog/shops` -> `{shops: Shop[], source_revision: number, fetched_at: ISO8601}`.
- GET `/api/operations/catalog?shop_key=...` -> CatalogSnapshot.
- GET `/api/operations/catalog/product?shop_key=...&sku=...` -> ProductSnapshot.

Shop: `{shop_key, name, platform, currency, timezone}` (strings).

CatalogSnapshot: `{shop: Shop, products: Product[], source_revision: number, fetched_at: ISO8601, data_mode: "mock_source"}`.

Product:
```
shop_key: string; sku: string; name: string; image_url: string | null;
unit_cost: string | null; currency: string;
available: number | null; inventory_observed_at: string | null;
last_sold_price: string | null; last_sold_at: string | null;
order_count: number; review_count: number; negative_review_count: number;
return_order_count: number;
```

ProductSnapshot: `{shop: Shop, product: Product, reviews: Review[], orders: Order[], returns: Return[], source_revision: number, fetched_at: ISO8601, data_mode: "mock_source"}`.

Review: `{review_id, order_id, reviewed_at, rating: number, body}`.
Order: `{order_id, ordered_at, status, quantity: number, unit_price: string}`. Multiple same-SKU lines in one order may return separate rows; order_count counts unique orders.
Return: `{return_id, order_id, requested_at, reason, status, refund_amount: string}`. These are returns on related orders, NOT a returned-SKU assertion.

Money is a decimal string in major units. Unknowns stay null. Stock sums only the newest observation per location; partial unknown stock stays null. All source reads for one response must share one revision; bounded retry or sanitized 503 on concurrent change. No silently truncated pagination. No frontend fixture fallback.

Missing/forbidden shops or SKUs -> 404; invalid selection -> 422; unconfigured/outage/inconsistent source -> sanitized 503 `{detail: string}`. Existing health/incidents/navigation still work when the optional catalog integration is disabled.

Runtime: `SHOP_CATALOG_MODE=disabled|source` (direct Python default disabled; Docker default source). Source mode requires `CRONJOB_SERVER_URL` and server-side `SHOP_DATA_USER_ID`; fail startup for missing/invalid required config. HTTP adapter uses cronjob `/v1/mock/{resource}` and the configured internal source identity. No public arbitrary proxy routes or admin access. Tests inject a provider or HTTP transport; production reads no sibling service files.

Every read checks current source access and revision. Catalog/product cache hits reuse only the same source/principal/shop/revision and preserve the original coherent evidence `fetched_at`; shop-list timestamps reflect their fresh fetch. Read-only deployment preflight: `python -m app.catalog_check` emits status/counts/revision only, fails empty by default, and accepts an intentional empty dataset with `--allow-empty`. The existing data services use explicit `POSTGRES_PORT=15432` for this deployment target; runtime configuration/live source verification is separate from offline tests.

Browser routes: `/shop/products?shop_key=<encoded>&sku=<encoded>`; absent SKU shows gallery. `/shop/overview` remains compatible; Products is a prominent navigation destination while Connections remains the default entry from PR #14. Explicit selection appears in the address/history and survives tab switching. Optional source image_url passes through when available; missing images remain honest placeholders.
