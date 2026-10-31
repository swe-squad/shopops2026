# Shop Data integration contract — T10 draft

Status: proposed contract; remote profile is NOT activated. Database projection and
cross-service acceptance remain outstanding. Catalog validation alone proves neither
isolation nor correctness of the published data.

## Committed inputs

- Task plan: `15202f5`.
- T09 fixes: `311aa4e` and `e34056f`; their acceptance must still be verified.
- Data MCP: `e663f88`.
- Pipeline: `5262ba4`.
- Local combined base: `09a30a1`, branch `feat/agent-core-data-mcp`, worktree
  `/tmp/shopops2026-agent-core/T10`.

Dependency merges import existing upstream files; new implementation stays in the
T10-owned service paths. No deployment or paid hosted execution is authorized here.

## Identity and transport

The trusted binding is `(tenant-a, alice, shop-a)` to the synthetic source identity
`+84900000001` and shop `shopee-open-platform:1001`. Bindings require an immutable
ID, version and digest pinned by conversation configuration. Phone values belong only
in trusted configuration and `X-Phone-Number` headers, never model inputs, sources or logs.
Every data call includes the selected shop. Membership and per-shop database login
checks remain authoritative. Knowledge/history retain the existing scoped HMAC protocol.

Proposed profile: `shop-data-read-v1`; proposed registry revision:
`returns-hosted-data-v1`. Missing configuration must fail closed, never use fixtures.
The only public tools remain metrics, review summary, knowledge and history.

## Proposed projection contract

Each relation is `mcp_data.<dataset_id>`, has catalog layer `mart`, and is filtered
through the existing `mcp_access.current_shop()` restricted-login boundary.

| Dataset | Exposed columns | Grain |
| --- | --- | --- |
| agent_snapshot_v1 | source_revision, published_at, analysis_as_of | One published snapshot for selected shop |
| agent_sku_catalog_v1 | sku | Known selected-shop SKU |
| agent_order_cohorts_v1 | sku, order_id, business_date, has_return | Distinct shop/SKU/order |
| agent_review_facts_v1 | sku, business_date, review_id, source_document_id, negative_rating, sizing_mentions | Distinct selected-shop review |

No raw review bodies, buyer contacts or arbitrary JSON are exposed. Unknown SKU is
not equivalent to a known SKU with zero orders. Missing publication is unavailable.
`validate_catalog` rejects the legacy period catalog, missing/duplicate projections,
raw layers, unapproved relations and unexpected columns. It is preparatory code,
not yet called by an active profile.

## Metric semantics

Dates are inclusive Asia/Ho_Chi_Minh business dates, translated into half-open
instants. Baseline immediately precedes the requested interval with equal day count.
Orders count distinct shipped/completed orders containing the SKU. Returns count
those orders with an observed order-level request before the frozen analysis cutoff;
this does not prove that this SKU was returned or a return completed. Duplicate lines
and return records must not multiply counts. Rates are percentages rounded to six
decimals, change is percentage points, and zero denominators produce null rates.

Reviews use rating <=2 for `negative_rating`; `sizing_mentions` additionally applies
the pipeline's case-insensitive `(chật|nhỏ|size)` rule. Categories overlap. Evidence
is a deterministic sample sorted by business date and review ID, capped at 20 safe
source references per category; counts cover the entire interval.

## Publication and unresolved coverage gate

Publication markers come from `sync.state` and its matching successful `sync.runs`
record, with `mart.settings.as_of` as analysis clock. All facts and metadata must
come from one SQL snapshot, or bounded queries with equal publication/clock markers.
`queried_at` is not publication time or proof of interval completeness.

Operator decision: use a configured, independently verified complete-history start
for the synthetic demo dataset. Pin that date together with the binding version in
each conversation; a revision change requires a new conversation. Verify the bound
against the seeded-data oracle before activation. The request AND its equal-length
preceding baseline must fit between this date and the published analysis cutoff.
`validate_coverage` enforces those interval boundaries, including the complete final
local day and a timezone-aware cutoff. Never derive the bound from the first observed
order/review. Publication time and query time do not establish coverage.

## Result and error boundary

Use fixed catalog queries, validated SKU/date parameters, the explicit selected shop
and a total 15-second tool deadline. Validate result ownership, expiry, columns,
numeric types and provenance. Reject truncated/input-truncated responses and mixed
revisions. If preview is incomplete, read only an owned unexpired result within the
same budget. No partial success or fixture fallback is allowed.

Invalid arguments map to invalid_input; ownership/membership failures to
permission_denied; missing known entities to not_found; timeout to timeout; malformed,
incomplete or incompatible remote data to upstream_unavailable. Successful Core
results retain schema_version=1 and the 32 KiB limit. Source references must encode
actual dataset/result/publication identity without private endpoints or phone values.

## Outstanding acceptance

Projection migration, restricted-role tests, adapter and header policy, versioned
bindings/registry, demo alignment and the real PostgreSQL/HTTP mutation oracle remain
unimplemented. Hosted proof remains separately gated by T08/T09 acceptance and opt-in.
