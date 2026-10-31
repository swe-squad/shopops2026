---
title: "Protected shop data MCP"
description: "Implement PostgreSQL analysis, approved raw investigation, temporary marts and automatic collection through authenticated MCP."
status: in-progress
priority: P1
effort: "8-12 engineering days after integration contracts are supplied"
branch: codex/shop-data-mcp-design
tags: [backend, database, auth]
blockedBy: []
blocks: []
created: 2026-10-31
---

# Implementation plan

Outcome, constraints, non-goals and acceptance criteria are in the [design](../reports/research-20261031-data-mcp-design.md). The [configuration contract](../../docs/shop-data-mcp-configuration.md) owns environment names, deployment topology and operator checks.

Confirmed: PostgreSQL on VPS; Codex Agents API; public authenticated MCP HTTPS; private database; dev only; temporary ad hoc marts; owner approval for raw investigation; automatic bounded fresh pulls. No publishing of temporary marts into shared BI definitions.

| Phase | Status | Dependencies | Estimate |
|---|---|---|---|
| [1. Service, identity and query protection](phase-01-protected-query-service.md) | Implemented locally; live wiring pending | Database schema/version, identity contracts | 4-6 days |
| [2. Temporary marts, integrations and deployment](phase-02-integrations-and-deployment.md) | Adapters implemented; live wiring pending | Phase 1, raw-approval and ingestion/processing contracts | 4-6 days |

## Work checklist

- [x] Preserve design and configuration documentation on the feature worktree.
- [x] Validate current repository paths, template commands and configuration consistency.
- [ ] Obtain missing contracts and remind owner at implementation/deployment checkpoints.
- [ ] Complete Phase 1 with isolation and authentication evidence.
- [ ] Complete Phase 2 with all live integrations and dev deployment evidence.

## Validation Log

### Session 1 — 2026-10-31

Three questions asked: connection origin, deployment environments, and whether ingestion/processing plus owner identity/raw-approval contracts exist. Answers: public authenticated HTTPS/direct OpenAI connection; dev only; "not yet, mark this and remind me in the future". These decisions are propagated into both phases and the configuration guide. Reminders are implementation checkpoints; no scheduled notification is claimed.

### Verification Results

Tier: Light (two phases). Ten source claims checked: five per phase. Verified: 9; Failed: 0; Unverified: 1 (sample mart contract absent from this worktree). Missing external integration contracts are explicitly unresolved dependencies, not verified existing implementations. Detailed evidence is in [validation report](validation.md). No live service or database tests were performed for this documentation change.

### Whole-Plan Consistency Sweep

Files reviewed: this index, both phases, design report and configuration contract. Confirmed topology, dev-only scope, raw approval, automatic collection and inherited temporary-mart permissions agree. Runtime implementation remains pending. No unresolved contradictory product decisions; external integration contracts and an approved schema/catalog fixture still block end-to-end implementation and deployment. No live task surface was available; checklists are the durable task state.

## Handoff

The documentation delivery is complete. Service code and tests are implemented under services/shop-data-mcp. Follow its HANDOFF.md to supply real schemas, issuer and upstream services; remind owner before live integration. Do not claim deployment readiness until Phase 2 checks pass. Execute with ak-cook using this plan's absolute path after the prerequisites are resolved.

## Implementation update

Typed MCP tools, startup validation/preflight, protected SQL projections, shop-bound database logins, grant-aware temporary marts and durable operation/result records are implemented. Local protocol/unit tests and disposable PostgreSQL isolation checks pass. Real upstream contracts and dev deployment evidence remain required; earlier validation entries describe the design-only snapshot.
