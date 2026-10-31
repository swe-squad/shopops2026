# Product investigation policy and real MCP seam

`returns-hosted-v2` in `config/registry-hosted.example.json` opts into the version `1.1.0` plugin
under `runtime-bundles/shopops-hosted-v1.1/`. The profile/bundle ID remains `shopops-hosted-v1`;
the packager selects an exact registered inventory by version. Per-file hashes and the aggregate
SHA-256 are checked before provider I/O. The `1.0.0` directory, old registry entry and legacy default
registry are preserved. Adding a revision does not activate it or replace saved conversations.

The product-investigation skill teaches scoped mart-first analysis, permitted raw drilldown,
freshness checks, conditional pull-latest and six seller workflows: reviews/returns, voucher margin,
cancellations/late shipments, inventory/demand, penalties, and payout/fee anomalies. The root owns
retrieval; compound returns keep actual data-analyst/knowledge-analyst children with bounded evidence.
Children have no function tools/MCP proxy. The unchanged helper writes the closed report-v1 only
from successful root-turn metrics and versioned policy evidence; no new artifact fields are added.

## What the current application actually grants

| Capability | Returned evidence | Explicit limit |
| --- | --- | --- |
| `get_return_metrics` | SKU/date counts, rates, preceding equal-length baseline, timezone and original data sources | Fixture aggregate, no raw return/order rows or completeness watermark |
| `get_review_summary` | SKU/date category counts and evidence reference strings | Reference strings are not fetched review text/raw records; categories do not prove cause |
| `search_knowledge` | Versioned document/chunk excerpts and matching knowledge sources | Policy evidence does not grant an operation or establish a merchant-specific cause |
| `get_conversation_history` | Owner/current-conversation messages and history sources | Historical context is not fresh shop evidence or a reusable approval |

Only the configured, backend-granted subset enters agent context. Successful envelopes include
observed_at; it is an observation timestamp, not proof of live marketplace ingestion or completeness.
Missing source revision, raw drilldown, coverage and freshness metadata stay unknown/unavailable.
Errors and not_found never become zero metrics. Current tools cannot fetch a catalog, issue a pull,
poll refresh state, edit listings/prices/vouchers/inventory, issue refunds or respond to reviews.

## Real MCP integration boundary

The AI engineer separately owns per-user runtime/team provisioning, registration identity and vault
storage, MCP authentication/transport and runtime-managed credential injection. The agent may use
only approved runtime-registered, backend-granted connections; it cannot read/print a vault/token,
infer identity from an input ID, request credentials or select another transport. An isolated
sandbox does not replace independent tenant/shop/product authorization in the MCP service.

The current executable seam is `app/agents/capabilities.py`, the closed arguments/results and
permissions in `app/tools/validation.py`, and the authorized dispatcher in `app/tools/bridge.py`.
`approved_remote_profiles` approves compatibility with those schemas only. It does not discover new
tools or widen scopes. Real mart/raw/refresh capability work must reconcile those definitions,
validation, routing, independent backend authorization, config pins, consumers and focused tests
together; do not rename a remote profile and claim new behavior. No such executable extension is
included in this policy change. Preserve existing snapshots or introduce a versioned contract.

For an engineer-granted raw capability, the schema must declare bounded reads/pagination and scoped
source references; returned revisions/coverage must let the agent relate raw evidence to the mart.
For a granted pull-latest capability, document exact permitted scope/data families, prerequisites,
request identity, status/reconciliation surface, retry/cooldown limits and evidence-read surfaces.
Expose observation/source/mart revision and coverage metadata with honest unknown/partial states;
raw pull completion does not imply historical backfill or a rebuilt mart. The skill never invents
names for these future tools or assumes a server uses its example status terms.

The policy preserves accepted/queued/running as pending, reconciles unknown before resubmission,
reports failed with prior evidence age, respects cooldown/retry_after, and rereads scoped evidence
after completion before calling it fresh. If status/read capability or metadata is missing, report
pending/unverified/partial. A refresh receipt proves no merchant change or business improvement.
Merchant writes require their own granted operation and exact scoped approval where required,
current-state recheck, uncertain-outcome reconciliation and authoritative outcome verification.

Offline tests establish instruction content, package integrity, pins and closed report compatibility.
They do not establish real MCP access, freshness, per-user hosted isolation or merchant outcomes.
The existing opt-in hosted smoke remains a `1.0.0` fixture workflow; separate live acceptance is
required after the engineer integrates the actual granted mart/raw/refresh schemas and transport.
