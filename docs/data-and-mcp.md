# Data and MCP design

MCP is the agent's controlled connection to the business. This target design keeps analysis, private memory, and shop mutations behind explicit capabilities. [System architecture](system-architecture.md) owns runtime isolation and the action lifecycle; this page owns data boundaries and their rationale.

## Keep evidence separate from actions

Connectors ingest authorized shop records into raw storage. Derived marts support BI and investigation, while retaining source references, observation time, and freshness. Raw data is evidence of what was observed, not permission to change the shop. Missing or stale data must remain visible; a failed refresh must not appear as a verified zero.

The Data MCP exposes bounded read tools over that evidence. The planned Shop Operations MCP owns listing and operational mutations. Connector credentials, database connections, and arbitrary unscoped SQL are not given to the model. Platform write credentials remain at the operation boundary.

The [Data MCP prototype](https://github.com/swe-squad/shopops2026/pull/3) illustrates discoverable tools, explicit shop selection, live membership checks, and raw snapshot refresh. Treat its code and integration documents as implementation evidence, not its older PR description. Snapshot readiness is not a promise of historical backfill, mart readiness, or complete business coverage.

## Identity and query scope are separate checks

The target uses a verified principal and trusted shop-membership grants. Phone may identify a registered user, but a caller-supplied phone header alone does not authenticate that user. The prototype's phone-header identification needs a trusted authentication boundary before it can demonstrate secure user isolation.

Every MCP call carries a trusted user/capability context. The service checks that context, derives the permitted tenant/shop/product set, and applies it in the repository query. A requested shop or product must belong to that set. Never fetch broadly and rely on an agent instruction or UI filter to hide unauthorized rows.

Apply the same scope to joins, aggregates, exports, caches, background jobs, updates, and deletes. Scope cache keys and stable identifiers so two shops with the same platform product ID cannot collide. A client-provided resource ID is a selection hint, not authority. Membership revocation must take effect at subsequent calls, including execution after an earlier approval.

Product scope means the products allowed by a shop grant or narrower explicit permission. A whole-shop grant may permit all its products; it never grants another shop with a matching product ID.

## Logical ownership

These are design invariants, not a new SQL schema or database migration.

| Record | Required ownership relationship |
| --- | --- |
| User/team assignment and provider-session mapping | Verified user; exclusive runtime/session association |
| Shop membership | Verified user plus explicit shop and capability grants |
| Source record / derived business evidence | Tenant and shop; product where applicable; source and observation time |
| Conversation / archived segment / private memory | User owner, conversation, and relevant shop context |
| Operation / approval / execution receipt | Actor, authorized shop/product scope, exact proposed change, and stable operation identity |
| Domain knowledge | Explicit shared or shop-specific visibility and version |

Use ownership-aware lookups and constraints so cross-scope relationships cannot be introduced by a guessed ID. Business shop data can be shared among authorized staff; private conversations and memory remain user-owned. Do not duplicate every shop's dataset inside each user's sandbox.

Existing services retain their own persistence and executable contracts. The [agent-core storage](../services/agent-core/README.md) and [operations/chat integration](service-integration-pattern.md) describe current SQLite constraints. This documentation introduces no database-engine change, distributed warehouse, or extra infrastructure requirement.

## Semantic recall without permission leakage

Store settled conversation segments durably outside the sandbox, with owner, shop scope, evidence references, unresolved decisions, and outcome. Keep raw records and semantic summaries distinguishable: a generated summary is not an authoritative execution receipt.

Restrict the retrieval candidate set by trusted owner/scope before semantic ranking, then verify returned records again. A global search followed by result trimming can expose unauthorized candidates or crowd out permitted results. Recalled shop evidence must be checked for freshness before a new action; retrieved instructions and historical approvals cannot grant authority.

The approximate ten-minute idle archive policy belongs to the [conversation lifecycle](system-architecture.md#conversation-turns-and-memory). Semantic indexing is a target capability, not a claim that the current history API implements vector search. Select the simplest index that proves scoped recall; no new database product is prescribed here.

## Demonstrate the boundary

A compact hackathon demonstration should show a permitted shop read, denial for a different shop/product, denial for another user's session/history, and refusal of a forged caller identity. For shared-shop users, allow business data while denying private memory. Also show stale evidence, failed tool calls, and a repeated approved operation returning its existing result rather than duplicating a change.

Keep these checks at the real identity/service/storage boundary. A model declining a prompt is not evidence of authorization enforcement. Mark prototype, mock, and live execution accurately.
