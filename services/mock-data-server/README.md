# mock-data-server

Persistent synthetic commerce source. FastAPI exposes typed CRUD and coherent
platform-shaped snapshots. This service owns PostgreSQL `mock.*`; the processor
communicates through HTTP only. See the root SPEC-mock-source.md.

Runtime configuration is provided by the environment. Never commit `.env` or
credentials. This service is internal in CapRover, with no public domain or port
mapping. The processor reaches it through `MOCK_DATA_SERVER_URL`.

| Variable | Meaning |
|---|---|
| POSTGRES_HOST | Required database host |
| POSTGRES_PORT | Port, default 5432 |
| POSTGRES_USER | Required username |
| POSTGRES_PASSWORD | Required secret |
| POSTGRES_DB | Required database name |
| POSTGRES_SSLMODE | PostgreSQL TLS policy, default prefer |
| PORT | HTTP port, default 8000 |

Database tests will run only against an explicitly isolated test database.

For the current ShopOps deployment target, the existing PostgreSQL listener uses port `15432`.
Set `POSTGRES_PORT=15432` in the app's runtime configuration with the existing host, database and
credentials; the generic code default `5432` does not select that listener. See the owning
[deployment route and product preflight](../../docs/deploy-flow.md#products-đọc-dữ-liệu-postgresql-hiện-có).
UI deployment must preserve this database and must not reseed or reset it.

## Local setup

Requires Python 3.14 and PostgreSQL 17. From this directory in POSIX/WSL:

```sh
make install
cp .env.example .env
# Edit database values, then export the environment:
set -a
. ./.env
set +a
.venv/bin/python -m app.cli migrate
.venv/bin/python -m app.cli seed --profile mvp
make run
```

Windows uses `.venv\Scripts\python.exe` and PowerShell process environment
variables. CLI commands do not load `.env` automatically. Demo database username
and database name are `postgres`; supply the password at runtime.

Migrations are transactional and checksummed. The Docker startup command runs
`python -m app.cli migrate` before starting Uvicorn; direct local Uvicorn startup
still requires the explicit migration command shown above. Startup never seeds
or resets data. Repeated seeding preserves edits. Seeding a nonempty, unseeded
source is rejected.

## Seed and identity

Ten active users (`+84900000001` through `+84900000010`), seven merchants, 21 shops
and 140 unique orders. Every user sees 20 orders: seven Shopee, seven Lazada and
six Shopify. Users 1–4 have separate merchants; pairs 5/6, 7/8 and 9/10 share
merchants and records. Associated entity data covers the business scenarios.
Shopify account health is unsupported. Larger processor regression fixtures
verify anomaly thresholds separately from this small default seed.

`X-Demo-User-Id` supplies a trusted internal phone identity, not verified login.
Owner/analyst/viewer memberships all permit demo CRUD. Admin routes trust the
private backend globally. Keep the app internal in CapRover using **Do not expose
as web app**.

## HTTP contract

Interactive contracts: `/docs`; machine-readable contracts: `/openapi.json`.
All writes require `Idempotency-Key` (1–200 characters). Retry the same key and
intent after a timeout; a changed intent with that key returns 409.

| Route | Operations |
|---|---|
| `/v1/entities/{resource}` | GET list, POST create |
| `/v1/entities/{resource}/record?...` | GET, PATCH, DELETE with full key query parameters |
| `/v1/admin/entities/{resource}` and `/record` | Same CRUD for users, merchants, merchant-memberships |
| `/v1/access?user_id=...` | Current merchant/shop grants |
| `/v1/snapshot` | One consistent revision with access, documents, counts and tombstones |
| `/health/live`, `/health/ready` | Process; database/migration readiness |

Lists accept `limit` (1–200, default 50), `offset` (default 0), and `shop_key` for
business entities. Unknown filters fail. Full record keys are:

| Resource | Key fields |
|---|---|
| users / merchants | user_id / merchant_id |
| merchant-memberships | user_id, merchant_id |
| shops | shop_key |
| products | shop_key, sku |
| promotions | shop_key, promotion_id |
| orders / settlements / fulfillment | shop_key, order_id |
| order-items | shop_key, order_id, line_id |
| reviews / returns / account-health | shop_key, review_id / return_id / event_id |
| inventory | shop_key, sku, location_id, observed_at |

```sh
curl --get http://localhost:8000/v1/entities/orders/record \
  -H 'X-Demo-User-Id: +84900000001' \
  --data-urlencode 'shop_key=shopify:1001' \
  --data-urlencode 'order_id=gid://shopify/Order/100000'

curl --request PATCH \
  'http://localhost:8000/v1/entities/orders/record?shop_key=shopify%3A1001&order_id=gid%3A%2F%2Fshopify%2FOrder%2F100000' \
  -H 'X-Demo-User-Id: +84900000001' -H 'Idempotency-Key: discount-001' \
  -H 'Content-Type: application/json' --data '{"seller_discount":"123.00"}'
```

Money uses major currency units with two decimal places and nullable unknowns.
Create requests require the event timestamps documented in OpenAPI. Business
clock: `2026-10-31T00:00:00+07:00`; deletion timestamps use real UTC. IDs are
shop-qualified. Lazada lines each represent one unit; native item states determine
the parent state. Shopify fulfillment means shipped.

Order deletion produces tombstones for its dependent records. Other referenced
parents require dependents to be removed first. Deleted keys remain reserved.
Deleted access identities remain inactive. Document IDs change only when payloads
change. The processor retains versions it observed, not intermediate unobserved
versions or a business audit trail.

## Verification and images

```sh
make ci
make test TEST_ARGS='tests/test_seed.py -q'
docker build -t mock-data-server .
# From repository root with processor test dependencies installed:
python scripts/test-mock-pipeline.py --suite all
```

Docker tests create their own database credentials and containers; cleanup only
touches resources created by that run. Images contain migrations/fixtures under
`app/` and run as UID 1001. Access logs are disabled to avoid logging phone/query
data. Set actual database host/TLS and credentials in CapRover App Configs before
deployment. On every container start (including deploys and restarts), pending
migrations run automatically before the API starts. Applied migrations are skipped
after checksum validation; a migration failure prevents startup and is reported
in container logs. The database must already exist, and its configured user needs
permission to create and alter this service's schemas and tables.

To populate demo data after the service starts, explicitly run
`python -m app.cli seed --profile mvp` inside its container. Seeding is not part
of automatic startup.
