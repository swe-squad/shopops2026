-- Additive T10 read-only projections in the derived database.
-- Apply after pipeline migrations and 002-pipeline-access.sql as trusted operator.
BEGIN;
CREATE VIEW mcp_data.agent_snapshot_v1 WITH (security_barrier=true) AS
SELECT s.revision AS source_revision, r.finished_at AS published_at, cfg.as_of AS analysis_as_of
FROM sync.state s JOIN sync.runs r ON r.run_id=s.last_run_id
CROSS JOIN mart.settings cfg
WHERE s.revision>=0 AND r.status='succeeded' AND r.applied_revision=s.revision
  AND r.finished_at IS NOT NULL AND mcp_access.current_shop() IS NOT NULL;

CREATE VIEW mcp_data.agent_sku_catalog_v1 WITH (security_barrier=true) AS
SELECT sku FROM core.products WHERE shop_key=mcp_access.current_shop();

CREATE VIEW mcp_data.agent_order_cohorts_v1 WITH (security_barrier=true) AS
SELECT DISTINCT i.sku, o.order_id,
  (o.ordered_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS business_date,
  EXISTS (SELECT 1 FROM core.returns r WHERE r.shop_key=o.shop_key
          AND r.order_id=o.order_id AND r.requested_at<cfg.as_of) AS has_return
FROM core.orders o JOIN core.order_items i USING(shop_key,order_id)
CROSS JOIN mart.settings cfg
WHERE o.shop_key=mcp_access.current_shop() AND o.status IN ('shipped','completed')
  AND o.ordered_at<cfg.as_of AND o.updated_at<=cfg.as_of;

CREATE VIEW mcp_data.agent_review_facts_v1 WITH (security_barrier=true) AS
SELECT r.sku, (r.reviewed_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS business_date,
  r.review_id, r.source_document_id, r.rating<=2 AS negative_rating,
  (r.rating<=2 AND r.body ~* '(chật|nhỏ|size)') AS sizing_mentions
FROM core.reviews r CROSS JOIN mart.settings cfg
WHERE r.shop_key=mcp_access.current_shop() AND r.reviewed_at<cfg.as_of;

REVOKE ALL ON mcp_data.agent_snapshot_v1, mcp_data.agent_sku_catalog_v1,
  mcp_data.agent_order_cohorts_v1, mcp_data.agent_review_facts_v1 FROM PUBLIC;
-- Grant only these additive projections to previously provisioned dedicated logins.
DO $$
DECLARE mapped record;
BEGIN
  FOR mapped IN SELECT role_name FROM mcp_access.shop_roles LOOP
    EXECUTE format('GRANT SELECT ON mcp_data.agent_snapshot_v1, '
      'mcp_data.agent_sku_catalog_v1, mcp_data.agent_order_cohorts_v1, '
      'mcp_data.agent_review_facts_v1 TO %I', mapped.role_name);
  END LOOP;
END $$;
COMMIT;
