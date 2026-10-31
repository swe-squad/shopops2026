-- Backend lookup: bind user_id from a verified session, never from client input.
-- This relation contains every user's grants; it is not a session-aware RLS policy.
CREATE OR REPLACE VIEW access.user_shop_access AS
SELECT u.user_id, m.merchant_id, mm.role, s.shop_key, s.platform,
       s.source_shop_id, s.name, s.currency, s.timezone
FROM access.users u
JOIN access.merchant_memberships mm USING (user_id)
JOIN access.merchants m USING (merchant_id)
JOIN core.shops s USING (merchant_id)
WHERE u.is_active AND mm.is_active AND m.is_active;
