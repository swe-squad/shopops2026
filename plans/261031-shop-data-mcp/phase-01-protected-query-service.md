# Phase 1: Protected query service

Status: pending. Estimate: 4-6 days. Owner: service implementer. Dependencies: confirmed PostgreSQL version/schema and trusted token/identity contracts. Context: [plan](plan.md), [design](../reports/research-20261031-data-mcp-design.md), [configuration](../../docs/shop-data-mcp-configuration.md).

## Requirements and steps

- [ ] Remind owner that identity/token and PostgreSQL schema details are required. Record contracts and field-disclosure rules before executing live queries. The originally inspected sample mart files are absent from this worktree; obtain an approved schema/catalog fixture instead of assuming they are tracked.
- [ ] Scaffold `services/shop-data-mcp` from `python-fastapi` with `scripts/new-service.sh`. Read the generated AGENTS.md. Pin compatible MCP/PostgreSQL/SQL parser dependencies; verify Agents API transport compatibility.
- [ ] Implement startup validation for the configuration contract, `/mcp`, sanitized liveness/readiness and authentication on all data/discovery paths. Document `.env.example`, CA mounts and required settings; never print credentials.
- [ ] Add versioned migrations for private control metadata, roles/RLS and catalog definitions. Keep operator migrations separate from runtime credentials. Confirm view and materialized-table isolation using the real schema.
- [ ] Implement catalog search/description and bounded mart SQL under shop-bound identities. Deny unsupported SQL, unsafe functions, source writes and mutable authorization context. Reset/isolate pooled connection state.
- [ ] Implement scoped raw access requests and raw query execution. Use trusted approval records; no model-callable approval grant. Raw-grant projection must enforce dataset, fields, time window and expiry at execution.
- [ ] Implement result handles, paging, cancellation and provenance. Recheck authorization on every read; no cross-shop metadata/cache exposure.

## Files and verification

Create service-local `app/`, `tests/`, `migrations/`, `.env.example`, README, Dockerfile, Makefile and dependency pins. Reuse the generated `service.json` python stack/8000 port; no shared workflow changes expected. Phase 2 extends the same service sequentially, not in parallel.

Run `make ci` in `services/shop-data-mcp` after implementation. Add meaningful PostgreSQL-backed integration checks for two shops, connection reuse, raw grants, role bypass, SQL mutation/unsafe calls and unauthorized result handles. Make integration execution an explicit service target included in its CI contract; do not assume the template currently provides it. Require passing evidence against the supported PostgreSQL version, not only mocked responses.

Success: arbitrary useful read-only mart analysis works; wrong shop/identity and unapproved raw reads fail; unknown metrics remain unknown; query/result budgets hold. Failure: stop external exposure and disable affected capabilities. Rollback: revert application image and additive migrations through reviewed rollback steps without dropping source schemas/data.
