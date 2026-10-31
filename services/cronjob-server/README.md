# cronjob-server

Internal FastAPI processor and MCP-facing commerce API. See the approved
SPEC-data-pipeline.md and SPEC-sync-control.md at the repository root.
Container port 8000; local development uses port 8001 when both services run.

Use Python 3.14 and the standard make install/run/ci/docker targets under POSIX/WSL.
On Windows use the equivalent .venv/Scripts/python.exe commands.

Required runtime variables: POSTGRES_HOST, POSTGRES_USER, POSTGRES_PASSWORD,
POSTGRES_DB, and MOCK_DATA_SERVER_URL. POSTGRES_PORT defaults to 5432;
POSTGRES_SSLMODE defaults to prefer. SYNC_INTERVAL_SECONDS defaults to 0
(disabled); positive integers enable periodic full synchronization.
PORT defaults to 8000. See .env.example for placeholders.

The current ShopOps deployment target uses the existing PostgreSQL listener on port `15432`.
Set `POSTGRES_PORT=15432` explicitly with the existing database/credentials, matching
`mock-data-server`. See the [product deployment route](../../docs/deploy-flow.md#products-đọc-dữ-liệu-postgresql-hiện-có).
The browser reads current source records through this service's HTTP facade; it does not read
PostgreSQL directly or use the frontend's in-memory connection flags as shop data.

The source URL is required and supplied at runtime. In CapRover use
http://srv-captain--mock-data-server-dev:8000 for dev, and
http://srv-captain--mock-data-server:8000 for production. Keep both services internal
with no public domain or port mapping. Never commit credentials.

Database tests use scripts/test_db.py and an isolated disposable PostgreSQL instance.

## Local setup

Start the migrated/seeded source first. From this directory in POSIX/WSL:

```sh
make install
cp .env.example .env
# Edit database values and source URL, then export the environment:
set -a
. ./.env
set +a
.venv/bin/python -m app.cli migrate
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001 --no-access-log
```

Windows uses `.venv\Scripts\python.exe` and PowerShell process environment
variables. CLI commands do not load `.env` automatically. Username/database are
`postgres` for the requested demo; credentials remain runtime-only. PostgreSQL 17
is used in verification. Migrations are transactional and checksummed. The Docker
startup command runs `python -m app.cli migrate` before starting Uvicorn; direct
local Uvicorn startup still requires the explicit migration command shown above.

Deploy **one replica and one Uvicorn worker process**. A PostgreSQL advisory lock
serializes work if another process starts accidentally. Keep the apps private.

## MCP-facing contract

Product source/facade/core contracts include optional HTTPS `image_url` values.
Migration `007_product_images.sql` adds the nullable `core.products` column;
snapshots populate it. Deploy this processor before the updated source and
follow the [product image backfill](../mock-data-server/PRODUCT_IMAGES.md).

`/docs` and `/openapi.json` expose concrete models, required headers and composite
keys. User routes require `X-Demo-User-Id: +84900000001`. This is a trusted internal
phone convention, not authentication. Admin routes trust the private backend.
Every write requires `Idempotency-Key` (1–200 characters).

| Route | Behavior |
|---|---|
| `/v1/mock/{resource}` | GET list, POST create in source |
| `/v1/mock/{resource}/record?...` | GET, PATCH, DELETE in source |
| `/v1/admin/mock/{resource}` and `/record` | CRUD users, merchants, merchant-memberships |
| `POST /v1/sync-runs` with `{}` | Persist a full sync; return 202 and run ID |
| `GET /v1/sync-runs` and `/{run_id}` | Caller-owned runs with currently authorized shop counts |
| `/v1/admin/sync-runs` and `/{run_id}` | Global operational inspection |
| `/v1/core/{resource}` and `/record` | Read all eleven processed core entities |
| `/v1/raw/documents` and `/record?document_id=...` | Observed immutable raw evidence |
| `/v1/marts/{view}` | Eight calculated views |
| `/v1/access/shops` | Current grants intersected with processed ownership |
| `GET/PATCH /v1/admin/mart-settings` | Frozen clock and positive recent/baseline day windows |
| `/health/live`, `/health/ready` | Process; database/migrations/worker |

Resource names and full query keys follow the [source contract](../mock-data-server/README.md#http-contract).
Source mutations return 202 with `mutation_status`, `source_revision`, `run_id`,
`sync_status`, and `status_url`. `applied` confirms the source mutation. Poll until
the run succeeds at that revision or later before expecting processed results.

```sh
curl --request POST http://localhost:8001/v1/sync-runs \
  -H 'X-Demo-User-Id: +84900000001' -H 'Idempotency-Key: manual-001' \
  -H 'Content-Type: application/json' --data '{}'

curl --request PATCH \
  'http://localhost:8001/v1/mock/orders/record?shop_key=shopify%3A1001&order_id=gid%3A%2F%2Fshopify%2FOrder%2F100000' \
  -H 'X-Demo-User-Id: +84900000001' -H 'Idempotency-Key: discount-001' \
  -H 'Content-Type: application/json' --data '{"seller_discount":"123.00"}'

curl http://localhost:8001/v1/sync-runs/REPLACE_WITH_RUN_ID \
  -H 'X-Demo-User-Id: +84900000001'

curl --get http://localhost:8001/v1/core/orders/record \
  -H 'X-Demo-User-Id: +84900000001' \
  --data-urlencode 'shop_key=shopify:1001' \
  --data-urlencode 'order_id=gid://shopify/Order/100000'
```

An uncertain source response leaves the mutation `pending`; it does not confirm
success. After three uncertain attempts, `SOURCE_OUTCOME_UNKNOWN` preserves the
intent. Replay the **same caller, key, method, query and body** to reconcile with
the same run ID. Changed intent returns 409. A definitive source rejection is
retained and does not enqueue publication. Failed synchronization does not roll
back a confirmed source write; a new manual run can publish it later.

Runs persist as `pending_mutation`, `queued`, `running`, `succeeded`, or `failed`.
Recovery uses durable intents and source receipts after restart. Transient failures
receive at most three automatic attempts with 1/2-second backoff. Validation errors
stop immediately. Operational timestamps and scheduling use real time. With a
positive interval, startup recovers accepted work, then schedules when idle; the
next run waits N seconds after queue drain. Missed ticks do not accumulate.
Manual runs work with interval 0.

## Processed data and filters

The processor owns `access`, `raw`, `core`, `mart`, and `sync`; it never reads or
writes `mock.*`. A complete validated snapshot publishes in one transaction.
Stale revisions, missing records without tombstones, ownership/reference errors,
incomplete documents and altered immutable IDs reject publication. Tombstones
reconcile children before parents. Raw versions and deletion evidence remain;
SQL mart views recalculate from the current core data.

Eight views: `order_economics`, `shop_daily`, `shop_window_metrics`,
`product_review_metrics`, `inventory_risk`, `promotion_performance`,
`issue_candidates`, `agent_context`. Existing sample formulas are preserved.
Unknown costs remain nullable; refunds are deducted once; Shopify fulfilled means
shipped; Lazada lines represent individual units.

Lists return `data`, `pagination` and revision metadata. `limit` is 1–200 (default
50), `offset` >= 0. Core lists support exact key-field filters. Mart lists support
their grain fields: shop and order/SKU/promotion/issue, plus currency or period
where present. Raw lists support document_id, platform, shop_id and resource.
`date_from` inclusive / `date_to` exclusive ISO date filters apply to orders,
reviews, returns, inventory, account-health, order_economics, shop_daily and raw
documents. Timestamp boundaries use the database session timezone (UTC in the isolated test
setup); shop_daily dates already use shop time.
Unknown filters are rejected.

All user reads resolve current source access. Source outages fail closed with
503. Shared users see the same records; membership removal hides core, marts, raw
history and run counts immediately. Other users' run IDs return 404. Historical
retention does not grant access. `applied_source_revision` exposes stale processed
data relative to current source reads.

Initial clock: `2026-10-31T00:00:00+07:00`, recent window 2 days, baseline 12 days.
The clock never advances automatically. Settings PATCH deliberately changes
windows; later syncs preserve them. Business event timestamps are explicit.
The larger regression fixture verifies 1,344 orders and 29 candidates (10/10/9)
plus a healthy control. Default MVP remains 140 unique orders, 20 per user.

## Verification and handoff

```sh
make ci
make test TEST_ARGS='tests/test_worker.py -q'
docker build -t cronjob-server .
# Repository root:
python scripts/test-mock-pipeline.py --suite all
```

Docker is required. Runners create isolated test credentials, databases and named
containers and clean up only their own resources. Pair options: `--suite crud`,
`--suite recovery`, `--suite all`; `--no-build` reuses local images. The test-only
fault proxy is excluded from service images. A dedicated read-only PR workflow
runs the pair suite; shared CI and deployment workflows are unchanged.

After SQL view changes, regenerate checked-in read DTOs with
`.venv/bin/python scripts/test_db.py --export-contracts`, then `make format`.
The image packages migrations under `app/` and runs as UID 1001. Access logs are
disabled; worker logs contain run IDs, stages, revisions and sanitized codes.
Set actual database host/TLS and credentials in CapRover App Configs before
deployment. On every container start (including deploys and restarts), pending
migrations run automatically before the API and worker start. Applied migrations
are skipped after checksum validation; a migration failure prevents startup and
is reported in container logs. The database must already exist, and its configured
user needs permission to create and alter this service's schemas and tables.
This implementation does not implement MCP/audit systems.
# MCP integration

The optional MCP bridge exposes `POST /v1/refreshes` and
`GET /v1/operations/{operation_id}?subject=...&shop_key=...`.
Apply migration `006_mcp_refreshes.sql` before starting the updated service.
Set `MCP_SERVICE_TOKEN` to a separate credential matching shop-data-mcp's
`ingestion_token`, and set `MCP_SUBJECT_USERS_JSON` to an operator-managed mapping
from trusted JWT subjects to source users (synthetic example:
`{"agent-a":"+84900000001"}`). Without these values access is denied. Each request
checks the bearer credential, current source membership and published shop ownership.
The legacy `X-Demo-User-Id` header does not authenticate the MCP bridge.

POST accepts `subject`, `shop_key`, `resource="snapshot"`, timezone-aware `start`/`end`
and `idempotency_key`. It atomically stores ownership/request/run, rejects changed
payload reuse (409), enforces a 300-second shop cooldown (429), a 100-run queue budget,
and a 365-day lookback ceiling. Receipts are retained for retries. Repeated requests
return the same operation. Polling requires the same subject/shop and current membership.

This pipeline synchronizes the entire source snapshot; the requested window is audit
context, not a source filter or historical backfill promise. States map queued/running/
succeeded/failed to queued/processing/**snapshot_ready**/failed. Successful polling
includes `refresh_mode="full_snapshot"`, `applied_source_revision`, and `coverage=null`.
The event-time cutoff in `mart.settings` does not change on refresh. No raw approval is
implied. The pipeline marks publication and run success in the same transaction.

MCP reads use a separate restricted login per shop in this service's derived database.
Apply shop-data-mcp's `002-pipeline-access.sql` after cronjob migrations and initial sync,
then provision its query roles and catalog. Never hand agents the writer credentials.
Set the MCP caller's `CRONJOB_SERVER_URL` to the private cluster URL
`http://srv-captain--cronjob-server-dev:8000` (dev) or
`http://srv-captain--cronjob-server:8000` (production); localhost is for local tests.

Keep cronjob-server and mock-data-server private with **Do not expose as web app** and
no Port Mapping. Their legacy demo/admin routes are not public authenticated APIs.
The MCP bridge does not make those existing routes safe to expose publicly.
