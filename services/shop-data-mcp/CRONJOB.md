# Cronjob CRUD tools

The MCP server exposes list, get, create, update (PATCH), and delete for every
resource in cronjob-server's `/v1/mock` and `/v1/admin/mock` facade. Each resource
has five named tools with concrete entity, key, and patch input schemas. Existing
catalog, SQL, raw-grant and refresh tools keep their behavior.

## Enable

In the operator-owned `MCP_CONFIG_FILE`, add `cronjob:read` for source reads and
sync-run inspection, and `cronjob:write` for source mutations. Retain `data:read`:

```json
{
  "scopes": ["data:read", "cronjob:read", "cronjob:write"],
  "cronjob_admin_phones": []
}
```

This is a fragment to merge into the existing configuration. Set
`CRONJOB_SERVER_URL` to the private cronjob origin and supply the existing
`ingestion_token` service credential. Missing integration configuration with
CRUD scopes enabled refuses startup. No new environment variables or dependencies
are required. Local development uses `http://localhost:8001`; CapRover uses
`http://srv-captain--cronjob-server-dev:8000` or
`http://srv-captain--cronjob-server:8000` for the corresponding environment.

Scopes are server-wide capabilities. CRUD source reads include complete entity
fields such as review text; they are separately enabled because they do not use
the SQL catalog projections or raw-access grants. Both CRUD scopes default off.

The existing `X-Phone-Number` request identity is forwarded as `X-Demo-User-Id`.
Callers cannot supply another actor, upstream URL or credential. Ordinary tools
select only currently authorized, operator-configured shops; cronjob also checks
current upstream membership. Creating a new shop is the one exception to local
shop selection: cronjob validates the caller's membership in the supplied
merchant. An operator must configure the new shop before using other MCP shop
tools on it.

Admin tools manage users, merchants and memberships across shops. They require
both the relevant CRUD scope and the caller's canonical phone in the
operator-owned `cronjob_admin_phones` allowlist, empty by default. The caller must
still pass the existing MCP membership lookup. The service's existing phone-only
identity model also applies to admin access: phone possession is not verified.

## Resources and keys

For each suffix below, tools are named `cronjob_list_<suffix>`,
`cronjob_get_<suffix>`, `cronjob_create_<suffix>`, `cronjob_update_<suffix>` and
`cronjob_delete_<suffix>`. Hyphens in upstream routes become underscores in names.

| Tool suffix | Record key fields | Access |
| --- | --- | --- |
| `inventory` | `shop_key`, `sku`, `location_id`, `observed_at` | Shop |
| `settlements` | `shop_key`, `order_id` | Shop |
| `fulfillment` | `shop_key`, `order_id` | Shop |
| `account_health` | `shop_key`, `event_id` | Shop |
| `reviews` | `shop_key`, `review_id` | Shop |
| `returns` | `shop_key`, `return_id` | Shop |
| `orders` | `shop_key`, `order_id` | Shop |
| `order_items` | `shop_key`, `order_id`, `line_id` | Shop |
| `products` | `shop_key`, `sku` | Shop |
| `promotions` | `shop_key`, `promotion_id` | Shop |
| `shops` | `shop_key` | Shop |
| `users` | `user_id` | Admin |
| `merchants` | `merchant_id` | Admin |
| `merchant_memberships` | `user_id`, `merchant_id` | Admin |

Lists accept `limit` (1–200, default 50), `offset` (nonnegative, default 0), and
`shop_key` for ordinary resources. Omitting the shop works only for a caller with
exactly one authorized configured shop. Admin lists do not accept a shop filter.
Get/update/delete take the complete record key as `key`. Create takes the full
entity as `data`. Update takes only changed fields as `data`; omitted fields stay
unchanged and explicit nulls are forwarded. Empty patches and key/immutable-field
updates are rejected. Upstream enforces record references and merged-record rules.

## Examples

```json
{"name":"cronjob_list_products","arguments":{"shop_key":"lazada:1001","limit":50,"offset":0}}
```

```json
{
  "name": "cronjob_create_products",
  "arguments": {
    "data": {
      "shop_key": "lazada:1001",
      "sku": "TEA-001",
      "name": "Green tea",
      "unit_cost": "2.50",
      "cost_basis": "purchase"
    },
    "idempotency_key": "create-tea-001-v1"
  }
}
```

```json
{"name":"cronjob_get_products","arguments":{"key":{"shop_key":"lazada:1001","sku":"TEA-001"}}}
```

```json
{"name":"cronjob_update_products","arguments":{"key":{"shop_key":"lazada:1001","sku":"TEA-001"},"data":{"unit_cost":null},"idempotency_key":"clear-tea-cost-v1"}}
```

```json
{"name":"cronjob_delete_products","arguments":{"key":{"shop_key":"lazada:1001","sku":"TEA-001"},"idempotency_key":"delete-tea-001-v1"}}
```

Writes require a distinct `idempotency_key` per intent (1–200 printable ASCII
characters without spaces). Reuse exactly the same key and payload after an
ambiguous timeout or retry. The adapter does not automatically retry writes.
Responses retain `mutation_status`, `source_revision`, `run_id`, `sync_status`
and `status_url`. `pending`, `unknown`, and `rejected` are not successful writes;
an applied source mutation can still have queued or failed derived synchronization.

Poll `cronjob_get_sync_run` with the receipt's `run_id`; use `admin: true` for an
admin-resource receipt (the allowlist is rechecked). The tool builds a fixed route
from a UUID rather than following the returned `status_url`. Ordinary runs are
owner-checked upstream, and returned shop counts are limited to configured access.
Run IDs from CRUD are separate from `get_operation`'s MCP refresh operation IDs.

## Contract and verification

`app/cronjob_models.py` is a consumer-owned wire contract based on cronjob-server's
source entity, facade, and sync-run APIs (provider checkout `bf665fa`, inspected
2026-10-31). It has no runtime imports from another service. When the upstream
contract changes, update these models and the independent resource examples in
`tests/test_cronjob.py` together.

Tests exercise all 70 route mappings through the official MCP client, authorization,
typed inputs, partial updates, mutation receipts and upstream failure handling.
A disposable stateful HTTP server exercises create/retry/read/update/delete with
the real HTTP client. These checks establish consumer behavior against the modeled
contract; they do not verify a deployed provider or its database synchronization.
