# Sources and schema confidence

Researched 2026-10-30. All fixture values were created locally; no marketplace seller data was downloaded. The implementation uses small source-shaped subsets, not complete API emulators. No third-party SDK schema was treated as authoritative.

## Sources used or consulted

| ID | Official source | How it was used / access result |
|---|---|---|
| S1 | [Shopee Open Platform](https://open.shopee.com/documents) | Intended authority. Fetch returned HTTP 403; official schema could not be inspected. |
| S2 | [Shopee v2 get_order_detail](https://open.shopee.com/documents/v2/v2.order.get_order_detail?module=94&type=1) | Attempted endpoint reference, also HTTP 403. Shopee field names and envelope are provisional modeling assumptions; validate in an authorized partner account. |
| L1 | [Lazada order integration guide](https://open.lazada.com/apps/doc/doc?docId=121327&nodeId=29616) | Official indexed text describes shop-scoped order IDs, item-level statuses, and separate unit records even for identical items. Used for order/item grain and normalization. Direct page is JavaScript-rendered. |
| L2 | [Lazada GetOrderItems reference](https://open.lazada.com/apps/doc/api?path=%2Forder%2Fitems%2Fget) | Endpoint reference consulted; direct rendering did not expose its full field schema. Minimal fixture fields require a live-response contract check. |
| L3 | [Lazada order API overview](https://open.lazada.com/apps/doc/doc?docId=120984&nodeId=30764) | Official indexed description confirms item detail retrieval; full interactive page could not be extracted. |
| L4 | [Alibaba/Lazada Open Platform migration notes](https://developer.alibaba.com/docs/doc.htm?articleId=120173&docType=1) | Official historical documentation names `voucher_seller`, `voucher_platform`, product and SKU identifiers. Used for discount funding distinction. Historical evidence is not a current compatibility guarantee. |
| L5 | [LazOP 2.0 overview](https://open.lazada.com/apps/doc/doc?docId=120248&nodeId=29586) | Official indexed text confirms review APIs, `/review/seller/list`, `/review/seller/reply/add` and seller metrics. Used for future connector capability planning, not exact review payload fields. |
| L6 | [Lazada getting started](https://open.lazada.com/apps/doc/getting_started) | Official indexed overview of review, reverse-order and promotion capabilities. Supplement fallback chosen because full response contracts were not inspected. |
| H1 | [Shopify GraphQL Order](https://shopify.dev/docs/api/admin-graphql/latest/objects/Order) | Inspected 2026-10 version (versioned request redirected to `latest`). Source for IDs, dates, currency, cancellation, fulfillment, discounts and line-item connection. Production integration should pin a supported API version. |
| H2 | [Shopify GraphQL LineItem](https://shopify.dev/docs/api/admin-graphql/latest/objects/LineItem) | Source for line ID, SKU, quantity and original unit-price MoneyBag. |
| H3 | [Shopify GraphQL InventoryLevel](https://shopify.dev/docs/api/admin-graphql/latest/objects/InventoryLevel) | Consulted for future inventory adapter. Current inventory is explicitly supplemental, not an InventoryLevel response. |
| H4 | [Shopify GraphQL Refund](https://shopify.dev/docs/api/admin-graphql/latest/objects/Refund) | Consulted for future refund adapter. Current return/refund records use the local supplement contract. |
| H5 | [Shopify REST Refund](https://shopify.dev/docs/api/admin-rest/latest/resources/Refund) | Initial research only; page notes REST is legacy. Implemented connector uses GraphQL-shaped orders instead. |
| P1 | [PostgreSQL data types](https://www.postgresql.org/docs/18/datatype.html) | Typed relational core, exact numeric money and JSON storage choice; implementation targets PostgreSQL 17-compatible SQL. |
| P2 | [PostgreSQL timestamps](https://www.postgresql.org/docs/18/datatype-datetime.html) | `timestamptz` for instants, explicit shop timezone for business dates. |
| P3 | [PostgreSQL JSON functions](https://www.postgresql.org/docs/current/functions-json.html) | JSONB construction/aggregation in agent context views. |
| T1 | [PGlite getting started](https://pglite.dev/docs/) | Embedded PostgreSQL execution and validation without a running Docker daemon. |

## What is actually implemented

| Entity | Shopee | Lazada | Shopify |
|---|---|---|---|
| Orders/items | Provisional API subset | API-inspired subset; grain verified, full field contract partially verified | Selected GraphQL fields |
| Products and seller costs | Demo supplement | Demo supplement | Demo supplement |
| Reviews | Demo supplement | Demo supplement; review endpoint existence documented | Demo supplement, no native review API claim |
| Returns/refunds | Demo supplement | Demo supplement | Demo supplement |
| Stock observations | Demo supplement | Demo supplement | Demo supplement |
| Promotion definitions | Demo supplement | Demo supplement | Demo supplement |
| Fees and payouts | Demo supplement | Demo supplement | Demo supplement, no Shopify Payments availability claim |
| Shipment deadline | Demo policy | Demo policy | Demo policy |
| Account penalties | Demo supplement | Demo supplement, no Shopee-like penalty API claim | Unsupported, no health rows |

`api_subset` means a synthetic selected-field example, not a certified production connector. For Lazada, the official guide verifies the key structural differences; some payload field/type details remain assumptions. `provisional_api_subset` explicitly flags the inaccessible Shopee reference. `demo_supplement` is our own schema and must never be sent to a marketplace endpoint.

## Next native connectors to validate

For Shopee, investigate order details, item/model stock, item comments, escrow details, vouchers, return details, shipment deadlines and account health in the authorized reference. Do not infer an API's availability or permission from this fixture. In particular, merchant COGS must come from the seller's records, not be inferred from a platform field with a similar name.

For Lazada, begin with `/orders/get` and `/order/items/get`; validate products, `/review/seller/list`, reverse orders, seller voucher and finance endpoints against the authorized market/account. Seller metrics are not automatically equivalent to penalty-point history.

For Shopify, expand the GraphQL selection to InventoryLevel, Refund/Return and discounts as needed. Reviews, merchant costs and payment-provider statements may require separate sources. Do not assume a Vietnam shop uses Shopify Payments. Pagination, scopes, permissions and live writes remain outside this data prototype.
