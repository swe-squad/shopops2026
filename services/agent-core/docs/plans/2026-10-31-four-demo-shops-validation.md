# Four demo shops validation

The user clarified that recovery of old chat history is not required for this delivery.
Existing stored data is preserved; no history/session reset is included.

Read-only live checks confirmed exactly four existing source shops. The first two
synthetic phones already authorize Shopee 1001/1002. The third authorizes Lazada 1001.
The fourth synthetic user exists and is active; an additive viewer membership in
merchant-demo-002 authorizes the existing Shopify 1001. The previous inactive
membership in merchant-demo-001 was preserved. Source API returned applied; processed
access confirmed Shopify 1001. No shops, orders or model inputs were created.

Direct calls through the production Core ShopDataAdapter against dev Data MCP returned
successful get_return_metrics results for SHIRT-M, 2026-10-24 through 2026-10-30, for
all four scoped bindings. This proves remote data access, not hosted-model completion.

Review identified the singleton operations navigation mailbox as a cross-account side
effect. New accounts are denied navigation with 403 before forwarding; the original
account's existing navigation behavior remains. Regression test observed RED then GREEN.

The new routing tests cover server-side grant denial, invalid config, four distinct
conversations with the same client message key, each owner's nonempty history,
owned artifact download and cross-account denial, restart/relogin without provisioning
another team, and the original namespace with preexisting conversation/artifact records.

Optional loopback tests initially exposed a preexisting fixture defect: activation of
returns-hosted-v2 attempted to overwrite that shipped immutable snapshot with a renamed
v1. The fixture now activates the already-registered v2 without rewriting it. Runtime
registry behavior is unchanged.

Final local validation: Core lint/format clean; 527 passed, 2 live tests skipped.
Chat API lint/format clean; AGENT_CORE_LOOPBACK=1 full suite: 118 passed.
One inherited Starlette/httpx deprecation warning remains; no test failures.
