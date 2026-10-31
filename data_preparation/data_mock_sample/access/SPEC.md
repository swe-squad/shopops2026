# User shop access

Answer which shops a trusted, authenticated user may read. Users belong to merchants
through memberships; each shop belongs to exactly one merchant. An active user with
an active membership in an active merchant may read every shop of that merchant.
Owner, analyst and viewer roles all grant read access here; write permissions are
outside this dataset. Unknown, missing, disabled and revoked identities return no shops.

Keep operational entity keys unchanged. Add merchant ownership to raw wrappers and
core shops, and merchant identity to agent contexts. Other core and mart rows resolve
ownership through shop_key. No copied user_id on business records: several users may
access the same record.

Source fixtures live in access/*.jsonl. normalize.py validates ownership before
writing core exports and seeds access tables before raw/core rows. SQL defines
access.user_shop_access; examples export the full access graph and per-user results.
Use a parameterized user_id from the server's verified session, never a client-chosen
identity. This is an access lookup contract, not a login implementation or database RLS.
The backend must join this relation on every data read. No credentials are included.

Acceptance: all four shops have known merchants; cross-merchant reads are excluded;
multi-merchant membership works; revoking membership or disabling a user/merchant
takes effect immediately; null/unknown users see nothing; replays do not duplicate
access; the original 1,344 orders and 29 issue candidates remain unchanged in count.

Run from data_mock_sample: npm install, npm test, npm run example.
Python unittest covers connector ownership validation; PGlite runs actual PostgreSQL
queries for allow/deny cases and scoped raw/core/mart reads. Follow existing Python
and SQL conventions; use parameterized queries and foreign keys. No service or live
authentication configuration changes are part of this work.
