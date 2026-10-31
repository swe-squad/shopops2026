# Shop Data MCP

An authenticated Streamable HTTP MCP server for PostgreSQL marts, approved raw analysis, private expiring temporary marts and bounded automatic collection requests. Port: 8000. Endpoint: `/mcp`. Not deployed yet.

For dataset registration and tool changes, start with [Data and tool changes](DEVELOPMENT.md).

## Configure

1. Copy `config.example.json` to an operator-owned secret file outside Git and `catalog.example.json` to a separate approved dataset file. Replace hosts, issuer and dataset projections with real values. Mount both JSON files and the PostgreSQL CA. Set `MCP_CONFIG_FILE` and `MCP_CATALOG_FILE` to their absolute paths. Existing inline `datasets` remain supported when no separate catalog is selected. Missing/invalid configuration refuses startup; no demo data is loaded.
2. Apply `migrations/001-control.sql` as an operator. Create a restricted control login with USAGE on `mcp_control`; SELECT/INSERT/UPDATE/DELETE on results and refreshes; SELECT only on revoked_tokens. It must have no application source-table access. Revoke PUBLIC schema/table access. Operator credentials never enter the MCP container.
3. Provision a unique, non-owner PostgreSQL query login per shop with no privileged attributes or role memberships. Grant only the sanitized catalog projections for that shop. Use RLS or shop-specific security views to enforce tenancy in PostgreSQL; catalog filters supplement this boundary. This service refuses privileged query identities but cannot prove arbitrary views/RLS are correctly authored. Verify two-shop isolation before connecting real agents.
4. Put that shop's query DSN and allowed dataset IDs in `shops`. Query connections are fresh per request and read-only, with statement timeout and restricted SQL. Both control and query DSNs require `sslmode=verify-full` plus CA material when loaded at startup. The SSL certificate must match the private hostname.
5. Configure an RS256 JWT issuer/JWKS. Required claims: `sub` (agent identity), `shop_key`, `scope` (space-separated), `iat`, `exp`, `jti`, plus matching `iss` and `aud`. Tokens last at most one hour. Every HTTP request checks revocation in `mcp_control.revoked_tokens`; insert a jti there to revoke it. Signing keys stay outside this service. Scopes: `data:read`, optionally `raw:request`, `raw:read`, `data:refresh`.
6. Supply approval and ingestion service URLs/tokens when implemented. Until then those tools return sanitized errors. `HANDOFF.md` defines their exact proposed contracts, including processing-stage reporting. The MCP never forwards the agent token to those services.

The catalog example's dataset names/columns are integration contracts, not migrations that create those marts. The data engineer supplies actual schema, projections, semantics and coverage/watermarks. Catalog updates require a restart. Do not include customer identifiers in semantic descriptions.

## Agent tools

`search_catalog`, `describe_dataset`, `query_mart`, `request_raw_access`, `query_raw`, `create_temp_mart`, `query_temp_mart`, `read_result`, `drop_temp_mart`, `request_refresh`, `get_operation`.

Use catalog IDs in SQL, e.g. `SELECT sum(gross_sales) AS sales FROM order_economics`. A raw grant restricts projected columns and the mandatory `[start,end)` time predicate. All raw grants are revalidated after execution and on result access. Saved artifacts bind the exact source grant; changes/revocation deny access even after materialization. Temporary results are queried as table `temp`; columns are text, so cast numeric fields explicitly. Results are capped, paginated and expire. Cleanup of expired rows occurs when the same shop next saves a result; access is denied immediately at expiry. Operators may also schedule deletion of expired `mcp_control.results` rows.

The supported SQL subset includes projections, arithmetic, aggregates, filters, joins and selected casts. CTEs, arbitrary functions, custom types, system relations, writes and role changes are rejected. Unsupported queries fail closed. Two query slots are available per process; set replica/global database limits for total VPS capacity. A result's `truncated` flag must not be ignored when using it as a temporary mart.

Refreshes enforce resource allowlists, maximum lookback, per-shop cooldown and persisted idempotency. Upstream must also enforce request/page/quota/concurrency budgets and deduplicate retries atomically: network failures can occur after job creation. Operations remain owned by the original shop and subject. The ingestion status contract includes processing; only `mart_ready` is ready for renewed BI analysis.

## Data engineer checklist

- [ ] Create the actual mart and sanitized raw projection views; expose only approved columns. Register logical IDs, time fields, business grain, units, null semantics and freshness in the catalog JSON.
- [ ] Create a query login per shop and deny source ownership/privileged role membership. Enforce shop scope in PostgreSQL, including through views and materialized copies.
- [ ] Apply the control migration separately; grant the control login only its required metadata/workspace permissions. Do not grant query logins access to `mcp_control`.
- [ ] Supply private hostnames, certificate CA, verified TLS DSNs and mounted config; run the preflight.
- [ ] Test at least two shops plus a raw-data grant before adding operational data. Query aliases and catalog IDs use simple lowercase identifiers.
- [ ] Implement collection/processing and approval APIs from HANDOFF.md, or provide equivalent adapters with the same security properties. Identity issuance is an application-team dependency.

For a shared physical table with a `shop_key` column, the operator can apply policies like the following **after adapting the identifiers**. This is illustrative provisioning, not an automatic migration of existing data:

```sql
-- Provision passwords out of band. Never make this login a source-table owner.
CREATE ROLE shop_shopee1001 LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB;
ALTER TABLE mart.order_economics ENABLE ROW LEVEL SECURITY;
ALTER TABLE mart.order_economics FORCE ROW LEVEL SECURITY;
CREATE POLICY shop_1001_read ON mart.order_economics FOR SELECT TO shop_shopee1001
  USING (shop_key = 'shopee:1001');
GRANT USAGE ON SCHEMA mart TO shop_shopee1001;
GRANT SELECT (order_id, gross_sales, contribution_margin, ordered_at)
  ON mart.order_economics TO shop_shopee1001;
```

Policies on existing tables can affect other services: inspect their access before rollout. Views require suitable security-invoker/security-barrier behavior or equivalent shop-specific isolation; a view owned by a privileged role may bypass base-table RLS. Raw access must use sanitized views, not unfiltered JSON payload columns containing personal data. The MCP's column/time projections add restrictions; they do not replace database tenancy controls.

## Run and verify

```sh
make ci
# Set MCP_CONFIG_FILE and MCP_CATALOG_FILE to the mounted split files first.
make check-config
make check-data
make run
```

`make ci` runs Ruff and unit/protocol tests. Real database tests require a **fresh disposable** PostgreSQL database with role/schema creation privileges, supplied through `TEST_DATABASE_DSN`; they create and remove test schemas/roles. Never point this setting at operational data. Docker is optional; any disposable PostgreSQL instance works. `make integration` requires this variable and runs the real isolation test explicitly.

The template's toolchain uses Python 3.13+. The Docker image contains only runtime code. Health is `/health`; `/ready` is authenticated and checks control storage and reports whether integrations are configured. Ready does not certify source policies or upstream behavior.

## Deployment

Create CapRover app `shop-data-mcp-dev`, Container HTTP Port 8000, HTTPS and Force HTTPS, without Port Mapping. PostgreSQL remains private. In the same cluster the database hostname follows `srv-captain--<postgres-app>`. Mount configuration/CA, add runtime env and provision dev image-deployment secrets using the repository setup script. Production is outside the approved deployment scope.

Use the Agents API service-origin MCP entry in [configuration guide](../../docs/shop-data-mcp-configuration.md), with a backend-issued shop-bound bearer token. The SDK supplies protected-resource metadata; this app also exposes it at `/.well-known/oauth-protected-resource/mcp`. Public authentication is mandatory except for that metadata and liveness. The issuer must supply its own OAuth metadata/authorization flow if required by the client.

Before enabling raw data, remind the owner to implement the approval/identity contracts. Before enabling automatic refresh, remind them to implement collection/processing contracts. No upstream service, live PostgreSQL policy or Agents API round trip is claimed verified by local tests.
