# Spec: data-pipeline

Status: approved by the user on 2026-10-31. Module: `data-pipeline`. Lives inside
`services/cronjob-server/`; depends on the HTTP contract in
[SPEC-mock-source.md](SPEC-mock-source.md). Shared decisions are in
[CAPABILITY-MAP.md](CAPABILITY-MAP.md).

## Objective

Transform complete mock-source snapshots into persistent access/raw/core data and
queryable mart results. Replaying unchanged source data must not duplicate rows,
double-count money, grow raw history unnecessarily, or change results. CRUD
deletions must remove current business records while retaining observed raw
evidence. The consumer must never load precomputed core/mart fixtures as a
substitute for exercising the source-to-core transformation.

## Tech stack and project structure

Use the same Python 3.14/FastAPI template as the source service, a pinned
PostgreSQL driver, and an HTTP client. The baseline template already pins HTTPX
for development; declare it as a runtime dependency if used for source calls.
Exact additional pins are established during implementation compatibility checks.

```text
services/cronjob-server/
  app/main.py                 Application factory and lifecycle
  app/source/                 HTTP snapshot/access client and typed contracts
  app/pipeline/               Snapshot validation, normalization, reconciliation
  app/connectors/             Shopee, Lazada, Shopify adapters
  app/storage/                Parameterized queries and transaction boundaries
  app/migrations/             Packaged access/raw/core/mart/sync migrations
  app/cli.py                  Migration command
  app/api/, app/jobs/          sync-control module responsibilities
  tests/                      Mapping, database, and end-to-end tests
  AGENTS.md, README.md, .env.example
  requirements*.txt, Makefile, Dockerfile, service.json
```

No runtime imports or shared tables connect this service to the source service.
Adapt existing connector/schema/view definitions into the service with provenance
comments and tests. Docker must package migrations and required test-independent
assets; deployment cannot depend on `data_preparation/` being mounted.

## Persisted objects and ownership

| Schema | Required objects | Behavior |
|---|---|---|
| `access` | `users`, `merchants`, `merchant_memberships`, `user_shop_access` view | Replicated source access graph; phone identity; retained inactive deleted identities |
| `raw` | `documents` | Append-only observed source resource versions and deletion evidence |
| `core` | `shops`, `products`, `orders`, `order_items`, `reviews`, `returns`, `inventory`, `promotions`, `settlements`, `fulfillment`, `account_health` | Current normalized source state, upserted by existing composite keys |
| `mart` | `settings` | Singleton frozen business clock and window lengths |
| `mart` | Eight views listed below | Calculated from current core state; no CRUD or upsert into views |
| `sync` | Applied source revision and operational run/retry/deletion state | Minimal synchronization metadata; contract owned by `sync-control` |

Preserve the baseline schema's types, keys, constraints, and source-reference
columns. Add phone format validation to `access.users`; `user_id` itself is the
phone string. If `phone_number` is retained for fixture compatibility, enforce
equality. Do not add a `user_id` owner to each commerce row: shared visibility
continues through user -> membership -> merchant -> shop.

`raw.documents` retains its existing wrapper and JSONB payload and may add
resource revision/receipt metadata. A historical document is never overwritten
when its source resource changes. Persist deletion markers as demo-supplement
raw evidence, with complete original keys and ownership. Access-only deletion
evidence belongs in minimal `sync` deletion metadata when no shop exists; do not
invent a platform/shop wrapper for it. This is synchronization bookkeeping, not
an incident/action audit subsystem.

## Processing contract

The control module invokes a typed pipeline operation with a persisted `run_id`
and, for a CRUD-triggered job, a minimum source revision. The operation yields an
applied revision, per-shop inserted/updated/deleted/unchanged counts by entity,
new raw-document count, and a terminal result. A failure supplies a stable error
code and stage; record payloads and credentials do not appear in run errors.

Each attempt performs these observable steps:

1. Fetch the entire `/v1/snapshot` through `MOCK_DATA_SERVER_URL`, with bounded
   connect/read timeouts. Validate schema version, revision, `complete`, counts,
   platforms, ownership, references, and all resource shapes before applying data.
2. Refuse a source revision older than the last applied revision. If it is below
   a mutation's minimum revision, retry/fail rather than report completion. An
   unchanged already-applied revision is a successful no-op. Reuse of a document
   ID with different immutable contents is a source contract error, not an update.
3. Normalize all three platform formats. Stage the full normalized result before
   beginning the transaction that changes published data.
4. Under one database-wide synchronization lock, atomically upsert access
   identities, append newly observed raw resource/deletion versions, reconcile
   explicit tombstones, upsert all current core entities in dependency order,
   apply access deletions as inactive retained identities, and record the applied
   revision. Publish the successful run marker in the same commit, or persist an
   equivalent applied marker that lets a recovered run prove the commit happened.
5. On any validation or database failure, leave all published access/raw/core data
   and the applied revision unchanged. Persist the failed run separately so the
   previous complete dataset remains readable. No per-shop partial commit in MVP.

An HTTP timeout, a missing document, an empty unexpected collection, or a dropped
row without an explicit tombstone must never trigger inferred deletion. Compare
the complete normalized snapshot against existing live keys: an unexplained
missing key fails the run. Valid explicit tombstones remove only matching keys
within their declared scope. Repeated tombstones are idempotent. Apply child
deletions before parents; reconcile changed parent/child relationships within the
same transaction. Never issue a blanket truncate/reload.

When a user/merchant is deleted after its dependents, retain its access identity
as inactive to preserve raw ownership references. Deleted shops and their
previously removed children can disappear from current core; historical raw
documents remain. Membership removals immediately cease granting reads through
the current source access lookup used by `sync-control`, even before replication.

No watermark/CDC, delta-fetch mode, message broker, historical backtesting,
per-shop parallelism, or multi-service distributed transaction is required.
Historical raw evidence covers versions actually observed by successful syncs,
plus the explicit deletion markers; it cannot reconstruct every intermediate CRUD
state between polls.

## Transformation and calculation rules

Existing [mapping decisions](data_preparation/data_mock_sample/README.md) and
[normalizer](data_preparation/data_mock_sample/scripts/normalize.py) are the
baseline behavior, subject to runtime validation and immutable document IDs:

- Shopee timestamps are Unix seconds; IDs and item/model line identity are
  preserved. Native order status uses the existing mapping.
- Lazada order IDs become text; unit items remain quantity-one source lines.
  Aggregate order status is `mixed` if mapped item statuses disagree.
- Shopify retains full global IDs and line quantities. `FULFILLED` maps to
  `shipped`, not `completed`; cancellation takes precedence.
- Unknown statuses map to `unknown`. Unsupported Shopify account-health data is
  distinct from a healthy account. Supplements supply products, costs, operational
  events, enrichment, and ownership through the explicit mock contract.
- Foreign keys and joins always include `shop_key`; repeated source IDs from
  different shops/platforms never collide.
- Use Decimal and PostgreSQL numeric for money. Missing costs/fees/payouts stay
  null. Do not treat missing values as zero or add cross-currency totals.
- Refunds reduce settlement-based economics once; returns are not an additional
  financial subtraction. Settlements are cumulative order summaries.
- Preserve source-document provenance, including order enrichment provenance.

Install these eight baseline SQL views:

| View | Required meaning |
|---|---|
| `order_economics` | Per-order gross sales, costs, expected payout, contribution margin, payout variance and completeness |
| `shop_daily` | Daily totals at shop/local-date/currency grain, without join fanout |
| `shop_window_metrics` | Baseline/recent cancellations, cohort returns, weighted fee rates and sample sizes |
| `product_review_metrics` | Review counts, negative rates and sizing mentions with evidence |
| `inventory_risk` | Latest per-location inventory, demand, freshness and days of cover |
| `promotion_performance` | Seller discounts, complete financial results and loss-order counts |
| `issue_candidates` | Existing nine deterministic issue types and stable issue keys |
| `agent_context` | Merchant/shop-scoped evidence packets derived from candidates |

Preserve existing formulas and thresholds. Views reflect the committed core data
on the next query; there is no asynchronous mart refresh phase. Each response
query runs with a consistent database snapshot when it combines rows with counts
or revision metadata. Empty candidate results from insufficient sample sizes are
valid and must not be presented as proof of a healthy shop.

Initialize `mart.settings` once with `as_of=2026-10-31T00:00:00+07:00`,
`recent_days=2`, `baseline_days=12`. Windows remain `[start,end)` as defined by
existing SQL. Synchronization never advances this business clock. Operational
job times and intervals use real UTC time. A deliberate settings edit through
the administrative API changes the fixed evaluation point but does not recover
historical core states. Source CRUD must use explicit business timestamps or
documented frozen-clock defaults, not silently substitute wall-clock dates.

## Commands

Required implementation interfaces, run from `services/cronjob-server/` in
POSIX/WSL with connection settings supplied:

```sh
make install
.venv/bin/python -m app.cli migrate
make run
make ci
.venv/bin/pytest tests -q
docker build -t cronjob-server .
```

Native Windows uses the corresponding `.venv\Scripts\` executables. Migrations
must be versioned and repeatable without destroying data. Existing fixture
`load.sql` is reference material, not a production migration mechanism.

## Code style

Follow template formatting/type conventions. Keep platform mapping separate from
HTTP and SQL; return typed normalized entities, not side effects from a mapping
function. Use bound parameters for all values and fixed allowlists for relation
names. Example of preserving native Shopify status semantics:

```python
def shopify_status(cancelled: bool, fulfillment_status: str) -> str:
    if cancelled:
        return "cancelled"
    return {"FULFILLED": "shipped", "UNFULFILLED": "open"}.get(
        fulfillment_status, "unknown"
    )
```

## Testing strategy and success criteria

Use pytest unit tests for adapters and real PostgreSQL integration tests for SQL
views, foreign keys, rollback, and locks. Run against isolated test schemas, never
the configured demo/production tables. No new percentage threshold is required;
every required behavior has direct assertions. Test the actual pipeline against
HTTP snapshots, not only helpers with already-normalized rows.

- A first full sync populates every applicable table and all eight views are
  queryable. Per-user visible order counts match the seeded source.
- Replaying the same revision leaves entity counts, raw history, financial
  aggregates, and candidate keys unchanged.
- Create/update/delete round trips through native source documents produce the
  expected normalized change, current metrics, and correct historical evidence.
- A failed record or truncated snapshot causes zero partial publication; the
  previous dataset and revision remain usable.
- Cross-platform ID collisions, shared users, unknown values/statuses, Lazada
  unit quantities, Shopify shipped semantics, and refund accounting are tested.
- Tombstones remove the correct children/parents once; missing rows without
  tombstones fail; inactive identities retain historical raw ownership.
- A process interruption after commit is recovered as the already-applied result,
  without duplicate raw records or repeated financial effects.
- Service-contained regression fixtures adapted from the existing full dataset
  reproduce 1,344 orders and 29 candidates (10 Shopee, 10 Lazada, 9 Shopify), with
  zero candidates for the healthy Shopee control. Adapt user IDs to phones without
  changing business values. This larger test dataset is separate from the default
  service seed and must not lower anomaly thresholds.

## Boundaries and open questions

- Always: preserve decimal/null/status semantics, validate source responses,
  retain observed raw evidence, perform atomic publication, and run `make ci`.
- Ask first: changing business formulas/thresholds, introducing incremental sync,
  changing the frozen-clock model, or extending downstream incident/action scope.
- Never: read `mock.*` directly, upsert mart views, infer deletions from failures,
  rewrite historical raw documents, log personal payloads, or commit credentials.

No unresolved processing decision blocks planning. Database host/TLS remain
deployment inputs recorded in the capability map; the seed layout is approved.
