# Evidence freshness and permitted pull-latest

The root calls only actual backend-granted MCP capabilities. The current four fixture tools have
observed_at and original sources on successful envelopes. They have no raw-record fetch or refresh
operation/status capability, source revision, coverage watermark or completeness guarantee. Report
those limits explicitly. Never interpret observed_at as ingestion completion or live Shopee access.

For a future real MCP integration, inspect the granted schema and returned metadata before using
these semantics. This reference defines no new tool names, arguments or status enum. Keep the
original fields and map only statuses the actual capability documents; an unmapped status stays
unverified. Do not inject new fields into current closed v1 tool/results or report-v1.

## Before drawing a conclusion

- Resolve permitted tenant/shop/product, exact requested dates and timezone. Backend authorization
  remains mandatory independently of the sandbox and the agent's chosen IDs.
- Separate event dates, observed_at, last successful pull, source/mart revision, derivation time,
  historical coverage, pagination, exclusions and missing sources whenever they are returned.
  Missing metadata means unknown, not complete. An empty complete result differs from absent data.
- Compare like-for-like definitions, denominators and intervals. Do not join different revisions
  into a single snapshot silently. A coherent older snapshot can support a labelled historical
  finding; a fresh timestamp cannot prove complete data or comparable marts.
- Preserve exact source type/reference pairs. Raw drilldown must trace back to the same scoped
  summary/revision or document the mismatch. IDs or specialist assertions are not fetched evidence.

## Request lifecycle, only when granted

1. Confirm that the actual granted schema authorizes refresh for the selected scope/data family,
   including cost/approval requirements. Read its documented request identity, status/poll surface,
   retry_after and request limits. If no such capability exists, report refresh unavailable and
   continue only with appropriately labelled existing evidence. Do not ask for credentials.
2. Issue a permitted request once and retain its identity/scope for reconciliation. Never broaden
   a product request into a shop-wide pull without an applicable grant and documented behavior.
3. Interpret the returned state using the real schema:

   | State meaning | Required behavior |
   | --- | --- |
   | accepted / queued / running | Request is pending. Poll the same identity only through a granted status/read surface, within retry limits and the turn budget. Do not claim fresh data or success. |
   | unknown / disconnected / ambiguous response | Preserve uncertainty. Reconcile the same request before another submission; never blindly repeat it. If reconciliation is unavailable, report unverified. |
   | failed | Report failure and the age/limitations of the last successful evidence. Follow only documented safe retry rules; failure never produces a zero metric. |
   | cooldown / rate-limited | Respect retry_after and the documented limit; retain old evidence as old. Do not spin, bypass limits or invent a new request identity. |
   | completed / ready | Re-read scoped evidence and verify dates, observed_at, source/mart revision and returned coverage before claiming the requested data is fresh. |

4. A successful raw pull can precede mart rebuilding, exclude a data family, cover only a current
   snapshot or omit historical backfill. If the reread is unchanged/stale/partial or no read/status
   capability is available, say pending, stale, partial or unverified as appropriate. Never certify
   completeness from a request receipt alone. Stop polling at documented limits; report pending.
5. Cite only successful returned evidence. A refresh receipt supports request status, not a merchant
   performance claim, issue resolution or shop mutation. Verify the relevant outcome over a suitable
   observation window after a separately authorized action; do not confuse ingestion with remediation.

Data refresh updates evidence under its own grant. It does not authorize a price/listing/voucher,
inventory, refund or review-response write. Shop Operations needs its own capability and precise
scope/approval. A seller asking for newer data is not approving a proposed merchant action.
