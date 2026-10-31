# Compact platform mock data

A small, self-contained extraction from `data_mock_sample` for building Shopee,
Lazada and Shopify mocks. It includes 4 shops, 16 orders and a few rows for every
core table. All identities, phone numbers and transactions are synthetic.

## Files

| File | Use |
|---|---|
| `schema.sql` | PostgreSQL tables, keys, constraints and user/shop access view |
| `seed.sql` | Complete, replayable seed matching the JSON samples |
| `samples.json` | Normalized rows grouped by table, e.g. `core.orders`; use directly in a mock server |
| `raw/shopee.json` | Shopee-shaped order samples and explicit demo supplements; includes both Shopee shops |
| `raw/lazada.json` | Lazada-shaped orders, per-unit order items and supplements |
| `raw/shopify.json` | Shopify GraphQL-shaped orders and supplements |
| `queries.sql` | Runnable examples for shops, orders, products and raw evidence |

For a database mock, run these commands from this folder against a fresh demo
database that already exists:

```powershell
psql -v ON_ERROR_STOP=1 -d shopops_mock -f schema.sql -f seed.sql
psql -v ON_ERROR_STOP=1 -d shopops_mock -f queries.sql
```

The files work without the original folder or its Python/Node tools. The schema
does not migrate older tables. Replaying `seed.sql` upserts its rows; it does not
delete rows removed from the sample or preserve manual changes to seeded identities.

## User ID = phone number

Store `user_id` and `phone_number` as the **same text string** in canonical
international format, including `+` and the country code. The schema checks equality
and the phone string's format. Use the same formatting when mapping a verified
login to this data. There are no passwords or login endpoints in these fixtures.

| `user_id` = `phone_number` | User | Shops the user can read |
|---|---|---|
| `+84900000001` | Alice | `lazada:1001`, `shopee-open-platform:1001` |
| `+84900000002` | Bob | `shopee-open-platform:1002`, `shopify:1001` |
| `+84900000003` | Agency analyst | All four shops |
| `+84900000004` | Revoked member | None |
| `+84900000005` | Disabled user | None |
| `+84900000006` | User without membership | None |

Access follows `access.users → access.merchant_memberships → access.merchants →
core.shops`. Active users with active memberships in active merchants can read all
shops of those merchants. `owner`, `analyst` and `viewer` grant read access here.

```sql
SELECT shop_key, merchant_id, role
FROM access.user_shop_access
WHERE user_id = $1
ORDER BY shop_key;
```

Bind `$1` from the backend's verified session phone. Apply the access join on every
data read, including reads for a requested shop; see `queries.sql`. This view lists
all users' grants and is not automatically filtered by the session. Write permissions,
login verification and database row-level security are outside this sample.

## Tables and identifiers

| Table | Rows | Row key / meaning |
|---|---:|---|
| `access.users` | 6 | `user_id` = phone number |
| `access.merchants` | 2 | `merchant_id` |
| `access.merchant_memberships` | 6 | user + merchant; role and active flag |
| `raw.documents` | 9 | `document_id`; platform/shop/merchant wrapper around a payload |
| `core.shops` | 4 | `shop_key`; merchant, platform, source shop ID, currency and capabilities |
| `core.products` | 12 | shop + SKU; name and unit cost |
| `core.orders` | 16 | shop + order ID; dates, status and discounts |
| `core.order_items` | 18 | shop + order + line ID; SKU, quantity and price |
| `core.reviews` | 10 | shop + review ID; order/SKU, rating and text |
| `core.returns` | 4 | shop + return ID; order, reason, status and refund |
| `core.inventory` | 24 | shop + SKU + location + observation time; available stock |
| `core.promotions` | 4 | shop + promotion ID; funding and dates |
| `core.settlements` | 10 | shop + order; fees, shipping, refunds and actual payout |
| `core.fulfillment` | 16 | shop + order; dispatch deadline and shipped time |
| `core.account_health` | 2 | shop + event ID; penalty points and expiry |

`shop_key = platform:source_shop_id`. Source ID `1001` repeats across platforms;
always join business rows by `shop_key` plus their entity ID. Merchant ownership
is stored on shops/raw wrappers; other core rows inherit it through `shop_key`.
Business rows can be shared by several authorized users, so they carry shop keys.

## Platform shapes and sample coverage

Each raw file has a `documents` array. Each document's `resource` identifies its
payload. `orders` and Lazada `order_items` are API-shaped subsets; `supplement` is
this project's demo contract for products, reviews, costs, inventory and other
operational data. Metadata wrappers are also project-owned. Shopee's native order
contract is provisional; these samples are not captured live responses or full API contracts.

| Platform | Native order list | Native order ID | Item shape |
|---|---|---|---|
| Shopee | `payload.response.order_list` | `order_sn` | `item_list`; item/model IDs and quantity |
| Lazada | `payload.data.orders` | `order_id` | Separate `order_items` document; one item row per purchased unit |
| Shopify | `payload.data.orders.nodes` | `id`, retaining `gid://shopify/Order/...` | `lineItems.nodes`; quantity on each line |

Four selected orders per shop illustrate a returned order (`100072`), a recent
promotion order (`100294`), an open order (`100326`) and a cancelled order (`100330`).
The healthy Shopee `1002` control has completed orders instead of the injected
open/cancelled cases. Shopify uses `shipped` for fulfilled orders, without inferring
delivery. Shopify has no account-health rows because its feed is unsupported here.

The source clock is **2026-10-31 00:00 +07:00**. Money is VND in major units;
normalized JSON uses decimal strings. Null financial values mean unknown, not zero.
Raw and normalized samples cover the same orders and retain matching source IDs.
This small population is for mock responses and schema examples; the original
dataset's anomaly thresholds and 29 issue candidates require its full population.
