# Which shops may this logged-in user access?

The access graph is `users → merchant_memberships → merchants → core.shops`.
An active user with an active membership in an active merchant may **read every
shop belonging to that merchant**. `owner`, `analyst` and `viewer` all grant read
access in this dataset. Write/action permissions require a separate policy.
No user receives access just because a source shop ID matches another platform.

| Demo user | Allowed shops |
|---|---|
| `user-alice` | `lazada:1001`, `shopee-open-platform:1001` |
| `user-bob` | `shopee-open-platform:1002`, `shopify:1001` |
| `user-agency` | All four shops through two merchant memberships |
| `user-revoked` | None: inactive membership |
| `user-disabled` | None: disabled user, despite an active membership |
| `user-unassigned` | None: no membership |
| Unknown, empty or null user ID | None |

Merchant One owns Alice's two shops; Merchant Two owns Bob's two shops. These are
synthetic account labels, not usable login credentials. There is no password,
token, session store or authentication endpoint in this sample.

## Query from a trusted backend

Map the verified login/session subject to `access.users.user_id`. Bind that value
as `$1` using the database driver's parameter API. The browser must not select the
user ID, merchant ID or membership used for authorization.

```sql
SELECT shop_key, merchant_id, role, platform, source_shop_id, name
FROM access.user_shop_access
WHERE user_id = $1
ORDER BY shop_key;
```

The view evaluates current memberships on each query. Revocation or disabling a
user/merchant takes effect on subsequent queries; do not authorize from the static
export or an old session's role list. The fixture clock does not freeze access.

Apply the same access join when reading **any** business data. A selected shop key
must still belong to the user; filtering by a client-selected shop alone is insufficient.

```sql
-- Orders: $1 is the session user; $2 is the requested shop.
SELECT o.*
FROM core.orders o
JOIN access.user_shop_access a USING (shop_key)
WHERE a.user_id = $1 AND o.shop_key = $2
ORDER BY o.ordered_at, o.order_id;

-- Agent packets: also scope shop_daily, issue_candidates and other marts this way.
SELECT c.context
FROM mart.agent_context c
JOIN access.user_shop_access a USING (shop_key)
WHERE a.user_id = $1
ORDER BY c.issue_key;

-- Raw evidence: scope both platform and shop ID, plus merchant ownership.
SELECT d.*
FROM raw.documents d
JOIN access.user_shop_access a
  ON a.platform = d.platform AND a.source_shop_id = d.shop_id
 AND a.merchant_id = d.merchant_id
WHERE a.user_id = $1 AND d.document_id = $2;
```

These queries are the application access contract. `access.user_shop_access`
contains grants for every user; it is not automatically bound to a session.
The backend must filter by the verified user ID on every read. Do not expose
database access or the complete fixture exports to end users. Database RLS is
not configured here; PostgreSQL's default table privileges do not isolate rows
([PostgreSQL row-security documentation](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)).

## Files, ownership and rebuilds

`users.jsonl`, `merchants.jsonl`, `merchant_memberships.jsonl` and
`shop_ownership.jsonl` are application-owned source fixtures. A marketplace response
cannot grant membership. `shop_ownership.jsonl` supplies `merchant_id` to generated
raw wrappers and core shops. Native marketplace payload shapes remain unchanged.
All other core rows and mart views resolve merchant ownership through `shop_key`;
agent JSON packets also carry `merchant_id`. `mart.settings` is global configuration.
Several users can read the same shop, so business rows do not contain one `user_id`.

From `data_mock_sample`:

```powershell
npm.cmd install
npm.cmd run generate
npm.cmd test
npm.cmd run example
```

`generate` rebuilds deterministic raw and core samples. `test` normalizes the raw
samples and executes real PostgreSQL allow/deny and business-metric checks through
PGlite. `example` rebuilds every walkthrough and exports the access graph and
per-user results to [access.json](../examples/raw-to-mart/access.json), plus
[user-shop-access.jsonl](user-shop-access.jsonl). These exports are admin/demo snapshots.

To change shop ownership, edit `shop_ownership.jsonl`, then run all three commands
above. To revoke membership, set `is_active` to `false`; do not remove the row and
expect upserts to delete it. Loading fixtures resets users/memberships to their demo
values, so never replay them into a live authorization database.

Use a **fresh dedicated demo database** for schema version 1.1. `load.sql` creates
the access schema, loads the generated seed and installs access/mart views in one
transaction. `CREATE TABLE IF NOT EXISTS` does not upgrade older tables. This is
not a migration for an existing production database.
