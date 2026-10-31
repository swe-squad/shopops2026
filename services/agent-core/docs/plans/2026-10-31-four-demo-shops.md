# Four existing demo shops

Goal: connect exactly four synthetic phone identities to four existing commerce shops.
Preserve the original Alice/shop-a namespace, revision and credentials. Old chat history
recovery is not required by the user; do not delete existing data.

Mapping: +84900000001 -> shop-a -> shopee-open-platform:1001;
+84900000002 -> shop-demo-002 -> shopee-open-platform:1002;
+84900000003 -> shop-demo-003 -> lazada:1001;
+84900000004 -> shop-demo-004 -> shopify:1001.

Use server-owned routing configuration and separate Core fixture credentials, immutable
revision/binding pairs and owner scopes. Phone-only login remains local/test only.
Do not allow request bodies to choose routes. Keep the current global shop/revision
as the original account's fallback; adding routes must preserve its namespace exactly.
No source shops, orders or provider inputs are created by registration checks.

Implementation plan (native execution, authorized by user):
- [x] Add failing login/routing tests for all four accounts, isolation, invalid routes,
  session restart and original namespace compatibility.
- [x] Add validated AGENT_CORE_DEMO_ROUTES_JSON and resolve shop/revision from authenticated
  server-owned identity for provisioning, conversation creation and namespaces.
- [x] Append three restricted Core identities, three binding records and three new Luna
  revisions. Preserve all existing immutable snapshots and fixtures.
- [x] Add offline Core checks for each credential's grant and binding/revision match;
  run both services' CI and cross-service acceptance where available.
- [ ] Review changes, commit, push and open PR into develop. Deploy through repo workflow.
- [ ] Apply additive dev routing/MCP configuration and source membership only as needed;
  verify four logins and owner-scoped data without submitting model inputs. Preserve DBs.

Review focus: forged shop selection; cross-account history/artifacts; mismatched bindings;
original stored sessions; missing/invalid routing; source grants unavailable for account 4.
