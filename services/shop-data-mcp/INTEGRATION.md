# Pipeline and agent integration

The MCP boundary is `agent service -> shop-data-mcp /mcp`. Queries use PostgreSQL
logins scoped to one shop; refreshes use `shop-data-mcp -> cronjob-server -> mock-data-server`.
The source database belongs to mock-data-server. MCP query DSNs point to cronjob-server's
**derived database**, containing `core`, `mart`, `raw`, and `sync`. The control DSN can
point to a separate database; it stores MCP results and refresh receipts. Legacy revocation
storage is retained for rollback. Never give MCP the pipeline writer or source data
credentials. Its separate membership login can read only the authoritative access view.

This integration targets [PR #6](https://github.com/swe-squad/shopops2026/pull/6), base
commit `55b89d552d5ff777125c2796751da1372d091a15`, plus its companion MCP bridge changes
(`app/api/mcp.py`, migration `006_mcp_refreshes.sql`). Deploy those changes before
enabling refresh. No service imports another service's application code.

## Database setup

1. Apply the mock-data and cronjob migrations and publish an initial snapshot. Shops
   must exist before provisioning query logins. Actual source keys include
   `shopee-open-platform:1001`, `lazada:1001`, and `shopify:1001`.
   In the authoritative **source database**, apply
   `migrations/005-source-membership.sql` after the source migrations, then
   `migrations/003-phone-membership.sql`. These are explicit per-database steps,
   not a numeric migration sequence across all databases. The source owns `mock.*`;
   migration 005 creates the security-barrier `access.user_shop_access` projection
   there. Do not use the derived database's similarly named snapshot view for auth.
   The projection exposes only `user_id` and `shop_key`, checks active users,
   memberships and merchants, and excludes tombstones on all four joined tables
   (including shops). Set the membership login password out of band. It receives
   only column SELECT on that projection, no source table access or writes.
2. Apply `migrations/001-control.sql` in the control database. Provision the control login
   with USAGE on `mcp_control` and SELECT/INSERT/UPDATE/DELETE on `results` and `refreshes`.
   It has no application data permissions. The legacy `revoked_tokens` table is unused.
3. Apply `migrations/002-pipeline-access.sql` **once in the derived database**, as a
   trusted operator with source SELECT privileges. It creates security-barrier views
   in `mcp_data` and an operator-only role mapping. It leaves the pipeline's base tables
   and writer permissions intact. Do not grant PUBLIC access to the source schemas/tables.
4. From this service directory, set `MCP_PROVISION_DSN` to the operator DSN out of band:

   ```sh
   .venv/bin/python -m app.provision --shop shopee-open-platform:1001 --role shop_shopee1001
   ```

   Provision each shop once. The tool creates a fresh restricted LOGIN, with no password.
   Set the password through your secret-management workflow and configure that login's
   DSN in `shops`. Re-running the same mapping is safe; reassigning a login is rejected.
   Do not grant query roles additional memberships, ownership, or base-table privileges.
   Remove `mcp_access.shop_roles` entries to revoke a database mapping. A deleted shop,
   or a shop recreated under another merchant, resolves to no accessible rows.
5. Use `catalog.example.json`, whose physical relations now exist in `mcp_data`. Choose
   allowed dataset IDs per shop. Raw `settlement_details` remains owner-approval gated;
   its `fee` is `core.settlements.fee_amount` and `captured_at` is the source document's
   capture timestamp. Review text, arbitrary evidence JSON and buyer contacts are excluded.
6. Mount config/catalog and the PostgreSQL CA. Runtime config still requires
   `sslmode=verify-full` and `sslrootcert`. Run `make check-config` and `make check-data`.

The query login is resolved through PostgreSQL `session_user`; caller-controlled session
settings cannot choose a shop. View security follows PostgreSQL's
[security-barrier view rules](https://www.postgresql.org/docs/17/sql-createview.html) and
[session identity rules](https://www.postgresql.org/docs/17/functions-info.html).
The SQL filter is additional to the MCP catalog/column restrictions. Connection poolers
must preserve the actual per-shop login, not reuse a shared backend identity.

## Refresh configuration and semantics

Set `CRONJOB_SERVER_URL` in the MCP runtime:

| Environment | URL |
|---|---|
| Local | `http://localhost:8001` |
| CapRover dev | `http://srv-captain--cronjob-server-dev:8000` |
| CapRover production | `http://srv-captain--cronjob-server:8000` |

There is no default dev upstream. `CRONJOB_SERVER_URL` overrides legacy JSON
`ingestion_url`. Set secret JSON `ingestion_token` to the same separately issued value
as cronjob-server's `MCP_SERVICE_TOKEN`. A URL without a token refuses MCP startup.
Phone identity does not replace this service credential.

In cronjob-server, set `MCP_SUBJECT_USERS_JSON` to an operator-owned mapping from the
MCP phone subject to its authorized source user. For synthetic local tests only:
`{"+84900000001":"+84900000001"}`. Tool arguments cannot override the phone subject
or select a shop outside its current membership. Cronjob-server verifies the service token, resolves this mapping, checks current
source membership and published shop ownership on every submission and poll. Missing
token/mapping or unavailable membership checks deny access.

Operation/grant GET requests include the phone subject in their query parameters under
the existing bridge contract. Disable or redact query strings in upstream/proxy access
logs, in addition to redacting phone headers; do not log raw request bodies.

The bridge implements `POST /v1/refreshes` and `GET /v1/operations/{id}`. Refresh uses
`resource="snapshot"`: PR #6 collects and publishes the **entire source snapshot**.
The requested `[start,end)` is policy/audit context, **not a historical backfill filter**.
All built-in catalog refresh resources therefore use `snapshot`. Arbitrary collection
resources are rejected. Raw data approval is independent from collection.

The status flow is `queued -> processing -> snapshot_ready`, or `failed`.
`snapshot_ready` means the source revision was atomically published with derived data;
the response includes `refresh_mode="full_snapshot"`, `applied_source_revision`, and
`coverage=null`. It never reports `mart_ready` or claims interval completeness.
The pipeline's `mart.settings.as_of` still controls event-time analysis and is not advanced
by a refresh. Compare the revision and catalog clock semantics before describing data as fresh.

Both services persist ownership and idempotency. Retry the same canonical request with
the same key after an ambiguous network failure. Cronjob stores the request and queued run
in one transaction, rejects changed payloads with 409, enforces a 300-second per-shop
cooldown for new keys, and limits queued/running refresh load to 100 runs. Its absolute
lookback ceiling is 365 days; MCP defaults to 30. Receipts are retained without automatic
deletion, so retries remain deduplicated. Never purge them while retries can still arrive.

Keep cronjob-server and mock-data-server private in CapRover (**Do not expose as web app**,
no Port Mapping). Their existing demo/admin APIs are not hardened public APIs; the new
MCP bridge does not change those routes' security model.

## Agent service

Set the caller's runtime `SHOP_DATA_MCP_URL` to
`http://srv-captain--shop-data-mcp-dev:8000/mcp` (dev) or
`http://srv-captain--shop-data-mcp:8000/mcp` (production). Configure MCP's advertised
`public_url` with its HTTPS MCP URL and set `MCP_INTERNAL_URL` to the internal
`SHOP_DATA_MCP_URL` value so transport host protection admits it. Other hosts remain
rejected. Send `X-Phone-Number` on every request, including initialize and tool calls.
No bearer credential is required for MCP; knowledge of the phone number grants access.
For an external agent, use the HTTPS MCP URL and a client supporting custom HTTP headers.

Set `membership_dsn` to the restricted login provisioned by
`migrations/003-phone-membership.sql` in the **authoritative source database**,
after `005-source-membership.sql` creates the live source projection. It reads
only `user_id` and `shop_key` from the live `access.user_shop_access` view. Every request
resolves membership again, excluding inactive users, memberships and merchants. The phone
must match `user_id` exactly (`+` and 8-15 digits); no local-format guessing occurs.

Call `list_shops` and pass `shop_key` to each data tool. One phone can access multiple shops;
queries are executed separately through each shop's restricted login. A missing shop selection
is accepted only for a single authorized configured shop. No tool argument can change the phone.
If a selected shop is missing or no longer authorized, the tool returns the stable
SDK denial marker `permission_denied` (for `query_mart`, text content is
`Error executing tool query_mart: permission_denied`, with `isError=true`). This also
applies when the phone still has access to another shop and HTTP authentication
succeeds. Clients should map only this exact marker to permission denial; other
SDK tool failures remain unavailable/invalid outcomes without exposing raw details.

Server configuration supplies `scopes`, defaulting to `data:read`; refresh also needs
`data:refresh`. Raw queries still require the external owner-approval service.

Call `search_catalog`, `describe_dataset`, and `query_mart`; for a refresh call
`request_refresh(resource="snapshot", start=..., end=..., idempotency_key=...)`, then
poll `get_operation`. Keep the idempotency key unchanged on retry. A typical query is
`SELECT currency, sum(gross_sales) AS sales FROM order_economics GROUP BY currency`.

## Verification

Unit/protocol tests: `make ci`. Real schema/isolation tests need a fresh disposable
PostgreSQL database and `CRONJOB_SOURCE_DIR` pointing to the cronjob service directory.
Source membership tests use `../mock-data-server` by default; set `MOCK_SOURCE_DIR`
when that source checkout lives elsewhere:

```sh
TEST_DATABASE_DSN='...' CRONJOB_SOURCE_DIR='../cronjob-server' \
  .venv/bin/python -m pytest tests/test_database.py tests/test_pipeline_database.py \
  tests/test_agent_projections.py tests/test_source_membership.py -q
```

From the repo root, after installing both services' dev dependencies:

```sh
services/shop-data-mcp/.venv/bin/python scripts/test-data-mcp-integration.py \
  --pipeline-root /path/to/pipeline-checkout \
  --pipeline-python /path/to/pipeline-checkout/services/cronjob-server/.venv/bin/python
```

The harness creates disposable source, derived and control databases, starts real local
HTTP source/cronjob services, seeds and synchronizes synthetic data, and calls MCP tools
through the official SDK. It verifies restricted queries, refresh publication, revision
reporting, retry deduplication and cross-shop denials. It removes its containers/processes.
Local test DSNs bypass TLS only inside the test setup; production startup remains strict.
Windows uses `Scripts/python.exe`; the harness selects Psycopg's supported event loop.

Rollback: disable refresh configuration first. Keep receipt tables while reconciling any
in-flight jobs. Remove shop mappings or revoke logins to stop queries; do not drop shared
pipeline schemas. The projection migration is independent of the pipeline's base data.

## T10 additive agent projections (preparatory)

`migrations/004-agent-projections.sql` adds sanitized SKU/day cohorts, review flags,
known SKUs and successful publication metadata. Apply it after pipeline migrations
and `002-pipeline-access.sql`, as the trusted operator in the derived database.
Existing mapped query roles receive SELECT on exactly these four new views; fresh
roles provisioned afterward receive the existing projection permissions. Source/writer
permissions remain unchanged. `catalog.agent.example.json` is the isolated four-dataset
catalog; enabling it additionally requires listing its IDs in the selected shop config.

The Core data profile is not yet activated. Its proposed contract is in
`../agent-core/contracts/shop-data-integration.md`. Missing publication yields no
snapshot row; consumers must reject that state. Configured demo history coverage is
separate from publication/query time and must be independently verified. No raw body,
customer data, refresh or CRUD permission is required by these views.

Run `tests/test_agent_projections.py` with the same disposable database environment
as the pipeline database tests. It verifies duplicate order/return records, category
flags, absent publication and two real restricted shop logins. It is not a full
pipeline-to-chat acceptance test.
