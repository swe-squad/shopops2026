-- Apply once in the authoritative mock-data-server SOURCE database after its
-- migrations, BEFORE 003-phone-membership.sql provisions the restricted login.
-- Do not apply this in the derived database, whose access view has another owner.
BEGIN;
CREATE SCHEMA IF NOT EXISTS access;
CREATE VIEW access.user_shop_access WITH (security_barrier=true) AS
SELECT u.user_id, s.shop_key
FROM mock.users u
JOIN mock.merchant_memberships membership USING (user_id)
JOIN mock.merchants merchant USING (merchant_id)
JOIN mock.shops s USING (merchant_id)
WHERE u.is_active AND u.deleted_at IS NULL
  AND membership.is_active AND membership.deleted_at IS NULL
  AND merchant.is_active AND merchant.deleted_at IS NULL
  AND s.deleted_at IS NULL;
REVOKE ALL ON access.user_shop_access FROM PUBLIC;
COMMIT;
-- Rollback: disable membership access, revoke/drop the membership login using
-- 003's rollback guidance, then DROP VIEW access.user_shop_access. Preserve mock.*.
