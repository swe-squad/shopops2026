---
status: complete
---
# Product workspace and MCP investigation

## Contract
- Outcome: Shopee-inspired product browsing and evidence inspection backed by the persistent mock shop; agent instructions use granted MCP capabilities for mart, raw evidence and permitted refresh workflows.
- Constraints: independent clients/builds; existing browser tabs and incidents remain usable; no credentials in browser/URLs/reports; identity comes from the backend. The AI engineer owns registration, per-user vaults, hosted sessions and MCP transport. Preserve report-v1 and existing read-only defaults.
- Non-goals: live Shopee writes, image generation, changing customer reviews, registration/vault implementation or claims of live hosted acceptance.
- Acceptance: authenticated catalog reads with coherent revisions; product selection/search/shop selection/deep links; honest missing images/prices/freshness; visible records refresh; returns/reviews evidence; legacy navigation and incident behavior; approved MCP investigation policy and focused regression coverage. Test responsive standalone/embedded clients.

## Design brief
Register: Product.
Scene: Vietnamese merchant inspecting products and returns on desktop or a phone beside chat.
Direction: Shopee-inspired seller catalog: commerce orange, gray canvas, white tiles, compact navigation and product evidence tabs; preserve ShopOps identity.
Color: Restrained; existing ivory/ink tokens plus local neutral catalog surfaces and accessible action orange (approximately oklch(0.51 0.17 35)).
Type: Existing Inter/system family, hierarchy by size/weight.
Signature: Product imagery and SKU-linked review/return evidence.
Dials: variance 3, motion 1, density 6.

## Phases / ownership
1. [API contract and adapter](phase-01-catalog-api.md) — API worker owns services/shopops-api/**.
2. [Product UI](phase-02-product-ui.md) — UI worker owns services/shopops-web/**.
3. [Agent investigation policy](phase-03-agent-policy.md) — agent worker owns services/agent-core/** except credential/auth/provider/session infrastructure.
4. Controller owns root docs, tests/workspace/**, integrated verification/review and plan state.
5. [Deployment data route](phase-04-deployment-data-route.md) — explicit PostgreSQL `15432`
   target, container source-mode default and read-only preflight; user selected preparation only,
   without live configuration inspection or deployment.

Phases 1–3 use the frozen [catalog contract](catalog-contract.md). No workers edit sibling services or root docs. Inspect and preserve other owners' changes.

## Integrated base
Fast-forwarded to develop `082006d` after PRs #12/#14 merged during delivery. Preserve the new chat
bridge and in-memory Connections demo. Products remains independent of those demo flags and reads
the persistent catalog service. Integrated checks passed on this base; no remaining merge conflicts.

## Verification
Focused API/frontend/agent tests, affected service CI, browser regression suite, rendered product states at phone/tablet/desktop, independent review, docs/journal reconciliation. No commits, pushes or deployment requested.

## Completion
Implementation and deployment preparation complete. See [verification](reports/delivery-verification.md). Live App Configs/PostgreSQL inspection, deployment and hosted MCP acceptance were not performed, per the agreed scope. AI engineer integration remains explicit in the [policy contract](../../services/agent-core/contracts/product-investigation.md).
