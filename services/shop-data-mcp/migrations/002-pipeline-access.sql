-- Apply as a trusted operator AFTER cronjob-server's migrations, in its derived DB.
-- Source tables/views remain pipeline-owned; no RLS changes affect the sync writer.
BEGIN;
CREATE SCHEMA mcp_access;
CREATE SCHEMA mcp_data;
REVOKE ALL ON SCHEMA mcp_access, mcp_data FROM PUBLIC;
CREATE TABLE mcp_access.shop_roles (
  role_name name PRIMARY KEY,
  shop_key text NOT NULL,
  merchant_id text NOT NULL
);
REVOKE ALL ON mcp_access.shop_roles FROM PUBLIC;

-- session_user is the authenticated login even inside owner-executed views/functions.
CREATE FUNCTION mcp_access.current_shop() RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog
AS $$ SELECT r.shop_key FROM mcp_access.shop_roles r
      JOIN core.shops s ON s.shop_key=r.shop_key AND s.merchant_id=r.merchant_id
      WHERE r.role_name = session_user $$;
REVOKE ALL ON FUNCTION mcp_access.current_shop() FROM PUBLIC;

CREATE VIEW mcp_data.order_economics WITH (security_barrier=true) AS
SELECT shop_key, order_id, ordered_at, currency, status, gross_sales, cogs,
       fee_amount, actual_payout, expected_payout, contribution_margin, payout_variance,
       financials_complete
FROM mart.order_economics WHERE shop_key = mcp_access.current_shop();

CREATE VIEW mcp_data.shop_daily WITH (security_barrier=true) AS
SELECT shop_key, business_date, currency, orders, cancelled_orders,
       unmapped_or_mixed_orders, finance_complete_orders, contribution_margin,
       fulfilled_gross_sales
FROM mart.shop_daily WHERE shop_key = mcp_access.current_shop();

CREATE VIEW mcp_data.shop_window_metrics WITH (security_barrier=true) AS
SELECT shop_key, period, currency, orders, cancelled_orders, cancellation_rate,
       fulfilled_orders, returned_orders, return_rate, settled_orders, effective_fee_rate
FROM mart.shop_window_metrics WHERE shop_key = mcp_access.current_shop();

CREATE VIEW mcp_data.product_review_metrics WITH (security_barrier=true) AS
SELECT shop_key, sku, period, reviews, negative_reviews, negative_rate, sizing_mentions
FROM mart.product_review_metrics WHERE shop_key = mcp_access.current_shop();

CREATE VIEW mcp_data.inventory_risk WITH (security_barrier=true) AS
SELECT shop_key, sku, available, oldest_location_observation, daily_units, days_of_cover
FROM mart.inventory_risk WHERE shop_key = mcp_access.current_shop();

CREATE VIEW mcp_data.promotion_performance WITH (security_barrier=true) AS
SELECT shop_key, promotion_id, currency, orders, finance_complete_orders, loss_orders,
       seller_discount, contribution_margin
FROM mart.promotion_performance WHERE shop_key = mcp_access.current_shop();

CREATE VIEW mcp_data.issue_candidates WITH (security_barrier=true) AS
SELECT shop_key, issue_key, issue_type, entity_key, severity
FROM mart.issue_candidates WHERE shop_key = mcp_access.current_shop();

-- Sanitized normalized settlement fields, never raw JSON or buyer contacts.
CREATE VIEW mcp_data.settlement_details WITH (security_barrier=true) AS
SELECT s.shop_key, s.order_id, s.fee_amount AS fee, s.actual_payout, s.paid_at,
       d.captured_at
FROM core.settlements s JOIN raw.documents d ON d.document_id = s.source_document_id
WHERE s.shop_key = mcp_access.current_shop();
REVOKE ALL ON ALL TABLES IN SCHEMA mcp_data FROM PUBLIC;
COMMIT;
