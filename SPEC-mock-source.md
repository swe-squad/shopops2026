# Spec: mock-source

Status: approved by the user on 2026-10-31. Module: `mock-source`. Provider service:
`services/mock-data-server/`. Initiative decisions and runtime configuration are
in [CAPABILITY-MAP.md](CAPABILITY-MAP.md).

## Objective

Provide a persistent synthetic commerce source that the processor can read and
mutate entirely through HTTP. A successful mutation must be reflected coherently
in both source CRUD reads and platform-shaped snapshot documents. Sample restarts
must never undo edits. This is a project-owned mock API, not a complete emulation
of marketplace authentication, routing, pagination, or rate limits.

## Tech stack and project structure

Use Python 3.14, FastAPI, typed Pydantic request/response models, and PostgreSQL,
following the existing Python template and pinned toolchain. Pin the selected
PostgreSQL driver when implementing. The service exclusively owns `mock.*`.

```text
services/mock-data-server/
  app/main.py                 FastAPI application and lifecycle
  app/api/                    Explicit entity, admin, and snapshot routes/models
  app/domain/                 Source validation and platform serialization
  app/storage/                PostgreSQL queries and transactions
  app/cli.py                  Migration and seed commands
  app/migrations/             Versioned, packaged SQL changes
  app/fixtures/               Synthetic seed inputs and scenario manifest
  tests/                      Unit, API, PostgreSQL, and snapshot contract tests
  AGENTS.md, README.md, .env.example
  requirements*.txt, Makefile, Dockerfile, service.json
```

## Seed and scenario contract

The default `mvp` profile implements the approved layout in the capability map:
ten phone-number users, seven merchants, one shop per platform per merchant, and
twenty orders visible to every user. Use synthetic phone numbers
`+84900000001` through `+84900000010`. Users 1-4 have individual merchants;
users 5/6, 7/8, and 9/10 share three further merchants. All users, merchants,
and memberships start active. Every pair sees the same twenty orders; business
rows have shop keys, not duplicate copies for each user.

Use a deterministic seed with `as_of = 2026-10-31T00:00:00+07:00`, a two-day
recent window and twelve-day baseline. Each merchant's seven/seven/six platform
split includes records before and within the recent window. The manifest lists
exact entity keys and expected scenario behavior, so coverage is executable.

Across each merchant's twenty orders and supporting records, cover normal
completed/shipped sales, open overdue shipment, cancellation, return/refund,
seller promotion loss, changed fees, payout mismatch, negative sizing reviews,
low stock, and account-health penalties on supported platforms. Include healthy
comparisons. Seed every applicable core entity type; Shopify health remains
unsupported with no fabricated health events. Do not require twenty rows of
products, reviews, returns, or every other entity.

Additional isolated test cases cover missing financial values, unknown/mixed
statuses, multi-line quantities, multiple inventory locations, repeated source
IDs across shops/platforms, and cross-merchant denial. They need not enlarge the
default seed. Existing full fixtures serve as regression inputs for all nine
issue types; they are not automatically loaded into the MVP source database.

Seed only on an explicit command into an empty source dataset. A repeated seed
command returns an already-initialized result without changing data. Do not seed
on each startup, overwrite user edits, or provide an automatic destructive reset.
The supplied compact `samples.json` and raw files are examples to expand, not two
independently editable stores that can diverge.

## Source data model

Keep typed source entity tables in `mock.*`; a single canonical source state
drives typed CRUD and platform serialization. Copy business fields from the full
dictionary/core schema with source-only mappings where needed. Generated
`source_document_id` and `enrichment_source_document_id` are output metadata, not
fields callers can choose. Marts are not stored in this service.

| API resource | Record key; fields follow the referenced dictionary |
|---|---|
| `users` | `user_id`; phone string is the sole identity; any `phone_number` field equals it |
| `merchants` | `merchant_id` |
| `merchant-memberships` | `user_id`, `merchant_id` |
| `shops` | `shop_key = platform:source_shop_id`; required `merchant_id` |
| `products` | `shop_key`, `sku` |
| `orders` | `shop_key`, `order_id` |
| `order-items` | `shop_key`, `order_id`, `line_id` |
| `reviews` | `shop_key`, `review_id` |
| `returns` | `shop_key`, `return_id` |
| `inventory` | `shop_key`, `sku`, `location_id`, `observed_at` |
| `promotions` | `shop_key`, `promotion_id` |
| `settlements` | `shop_key`, `order_id` |
| `fulfillment` | `shop_key`, `order_id` |
| `account-health` | `shop_key`, `event_id` |

Money is a decimal string in JSON and `numeric(18,2)` in PostgreSQL. Preserve
nullable money as unknown, not zero. Reject invalid phones, unsupported platforms,
incompatible currencies, invalid timestamp formats, impossible date ranges,
negative quantities/amounts where prohibited, invalid ratings, and unknown
request fields. Validate same-shop references even where the original fixture
schema does not declare an explicit foreign key, such as order/promotion linkage.

All key fields and ownership are immutable through PATCH. Re-keying or transferring
ownership requires explicit deletion/recreation. PATCH updates only supplied
fields; null clears only nullable fields. Create and patch models must be concrete
per-resource models, not unrestricted dictionaries or client-selected SQL tables.
Platform-only source identifiers/status fields required for serialization are
documented in each resource's OpenAPI model. Accept only native/normalized status
combinations that round-trip through the established mapping; do not fabricate a
delivered Shopify state. Lazada item statuses determine aggregate order status.

## HTTP provider contract

All routes use `/v1`. Fields use the existing dataset's `snake_case`; errors use
stable uppercase codes. Publish `/openapi.json` with typed inputs, outputs, and
examples for every resource, including key fields and nullability.

| Route | Behavior |
|---|---|
| `GET /v1/entities/{resource}` | List live business records, filtered by caller membership and optional `shop_key` |
| `POST /v1/entities/{resource}` | Create a business record; `201` |
| `GET /v1/entities/{resource}/record?...` | Read one record using its full key in query parameters |
| `PATCH /v1/entities/{resource}/record?...` | Partially update one record; `200` |
| `DELETE /v1/entities/{resource}/record?...` | Explicit deletion with a deletion receipt; `200` |
| `/v1/admin/entities/{resource}` and `/record?...` | Same CRUD verbs for `users`, `merchants`, `merchant-memberships`; trusted administrative caller only |
| `GET /v1/access?user_id=...` | Current active user identity and allowed merchant/shop keys; internal authorization lookup |
| `GET /v1/snapshot` | Complete consistent source snapshot for the trusted processor |
| `GET /health/live`, `GET /health/ready` | Liveness; readiness checks database and migrations |

Business resources include `shops` and all ten other core entities. Business
routes require the trusted `X-Demo-User-Id` header. An unknown/inactive caller gets
`403`; a missing or inaccessible record gets `404`. Collection results include
only allowed records. Creating a shop requires membership in its merchant.
Administrative routes intentionally permit the trusted backend to manage the
demo access graph globally; they do not claim to authenticate an end user.

Query-based keys avoid putting Shopify `gid://...` identifiers or inventory
timestamps into path segments. Clients use their HTTP library's parameter encoder,
including `%2B` for phone-number query values. List pagination uses `limit`
(default 50, maximum 200) and `offset` (default 0), sorted by the full record key.
Response: `{ "data": [...], "pagination": { "limit": 50, "offset": 0,
"total": 20 } }`. Multi-request listing is live, not a frozen snapshot.

Mutation success returns `{ "data": ..., "source_revision": 12 }`; a delete
returns its resource/key and `deleted: true`. Use a monotonic source revision,
incremented transactionally for effective writes. Errors use
`{ "error": { "code": "REFERENCE_CONFLICT", "message": "..." } }`:
`422` invalid input, `403` caller denied, `404` unavailable record, `409` duplicate
key/reference conflict/idempotency mismatch, `503` temporary dependency failure.
Do not expose database messages, payloads, or credentials in errors.

All mutations require `Idempotency-Key`. Atomically bind it to method, route,
record key, caller, and canonical body hash in the same database transaction as
the source mutation and saved response. Replaying the same intent returns the
original response without mutating again; different content returns `409`.
In-flight duplicates receive `409` with a retryable code. Retain receipts for the
MVP dataset lifetime, and never automatically reuse a key with an unknown outcome.

## Snapshot, raw shape, and deletion boundary

`GET /v1/snapshot` returns one bounded demo-sized response from a consistent
database snapshot; it has no ingestion pagination:

```json
{
  "schema_version": "1.0",
  "source_revision": 12,
  "complete": true,
  "as_of": "2026-10-31T00:00:00+07:00",
  "access": { "users": [], "merchants": [], "merchant_memberships": [] },
  "documents": [],
  "tombstones": []
}
```

The response also carries per-resource counts for completeness validation. The
empty arrays above illustrate shape, not a valid seeded dataset. A snapshot must
include every source entity, all access identities including retained inactive
ones, and all deletion markers needed for a fresh consumer. Partial failure
returns a non-success response; it must not return `complete: true`.

Each document has `document_id`, `merchant_id`, `platform`, `shop_id`, `resource`,
`source_kind`, `captured_at`, `resource_revision`, and `payload`. Preserve the
existing shapes: Shopee `response.order_list`, Lazada `data.orders` with a separate
unit-item response bundle, Shopify `data.orders.nodes`, and explicit supplements
for remaining entities. Supplements include order enrichments and shop metadata.
Serializing canonical entities must reproduce all supplied fields needed by the
processor, with no separate mutable raw copy.

Document IDs identify immutable resource versions; unchanged polls produce the
same IDs and content. A changed orders/items/supplement resource gets a new version
and document ID, and all affected representations change atomically. The snapshot
exposes current resource versions; the processor retains prior observed versions.
This is evidence at synchronization points, not capture of every intermediate edit.

Each tombstone has an immutable ID, source revision, resource, complete composite
key, merchant/shop scope where applicable, and deletion timestamp. Deleting an
order atomically tombstones its dependent items/reviews/returns/settlement/
fulfillment too. Deleting a product, promotion, shop, merchant, or user with live
dependents returns `409`; the caller deletes those dependents first. Deleting a
membership is allowed. Deleted access identities remain as inactive source
identities for historical references, while normal CRUD lists hide deleted rows.
Deleted business keys are reserved and cannot be recreated in this MVP.

## Commands

These are required implementation interfaces, not commands already available.
Run from `services/mock-data-server/` using the template's POSIX/WSL environment:

```sh
make install
.venv/bin/python -m app.cli migrate
.venv/bin/python -m app.cli seed --profile mvp
make run
make ci
.venv/bin/pytest tests -q
docker build -t mock-data-server .
```

Environment variables must be supplied before database commands. On native
Windows use `.venv\Scripts\python.exe` and `.venv\Scripts\pytest.exe` equivalents.
No reset command or deployment execution is required by this specification.

## Code style

Follow template Ruff rules, 100-character lines, typed functions, separate
create/patch/response models, parameterized SQL, and explicit resource allowlists.
Use async-compatible I/O in async handlers, or synchronous handlers for blocking
clients. Example of preserving unknown money:

```python
from decimal import Decimal


def money_json(value: Decimal | None) -> str | None:
    return None if value is None else format(value, ".2f")
```

## Testing strategy and success criteria

Use pytest for domain/API tests and a dedicated real PostgreSQL test database for
constraints, transactions, idempotency, and snapshots. Integration tests create
isolated test schemas and must refuse a non-test target. Existing PGlite tests are
supplementary, not substitutes for service integration tests. No new percentage
coverage threshold is imposed; each behavior below needs an executable test.

- Seed counts and each user's twenty visible orders match the manifest; shared
  users resolve to identical business keys without duplicate stored rows.
- Every listed entity supports create/list/read/patch/delete with valid references;
  create/update/delete survive service restart and a repeated seed command.
- CRUD changes serialize into all affected native/supplement documents and pass
  the processor's connector contract tests without dropping information.
- Same-key concurrent mutations and retries produce one effect; reused keys with
  different intent are rejected.
- Explicit order deletion produces complete child tombstones; other referenced
  parents reject deletion. No tombstone is generated for failed writes.
- Snapshots remain coherent while CRUD is happening; unchanged polls retain stable
  document versions. Deleted records never silently reappear.
- Invalid input, unknown users, and cross-merchant access are rejected; admin and
  user-scoped routes are separate and documented.

## Boundaries and open questions

- Always: persist changes, validate references, preserve decimal/null semantics,
  package fixtures/migrations in the service image, run `make ci` before commits.
- Ask first: changing the accepted seed interpretation, marketplace semantics,
  exposing the service publicly, or adding production authentication.
- Never: embed supplied credentials, reset live data on startup, import another
  service's code, expose arbitrary SQL, or fabricate unsupported platform data.

The 140-unique-order layout in the capability map is approved.
Database hostname/TLS are deployment inputs, not source API design blockers.
