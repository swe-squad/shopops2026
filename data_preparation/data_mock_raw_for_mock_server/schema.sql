-- Dedicated demo database. All money is in major currency units, not cents.
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS access;

CREATE TABLE IF NOT EXISTS access.users (
  -- Synthetic phone in canonical international format; user_id = phone_number.
  user_id text PRIMARY KEY CHECK (btrim(user_id) <> ''),
  phone_number text NOT NULL UNIQUE CHECK (phone_number ~ '^[+][1-9][0-9]{7,14}$'),
  CHECK (user_id = phone_number),
  display_name text NOT NULL,
  is_active boolean NOT NULL
);
CREATE TABLE IF NOT EXISTS access.merchants (
  merchant_id text PRIMARY KEY CHECK (btrim(merchant_id) <> ''),
  name text NOT NULL,
  is_active boolean NOT NULL
);
CREATE TABLE IF NOT EXISTS access.merchant_memberships (
  user_id text NOT NULL REFERENCES access.users,
  merchant_id text NOT NULL REFERENCES access.merchants,
  role text NOT NULL CHECK (role IN ('owner','analyst','viewer')),
  is_active boolean NOT NULL,
  PRIMARY KEY (user_id, merchant_id)
);

CREATE TABLE IF NOT EXISTS raw.documents (
  document_id text PRIMARY KEY,
  merchant_id text NOT NULL REFERENCES access.merchants,
  platform text NOT NULL,
  shop_id text NOT NULL,
  resource text NOT NULL,
  source_kind text NOT NULL CHECK (source_kind IN ('api_subset','provisional_api_subset','demo_supplement')),
  captured_at timestamptz NOT NULL,
  payload jsonb NOT NULL,
  UNIQUE (document_id, merchant_id)
);
CREATE TABLE IF NOT EXISTS core.shops (
  shop_key text PRIMARY KEY,
  merchant_id text NOT NULL REFERENCES access.merchants,
  platform text NOT NULL,
  source_shop_id text NOT NULL,
  name text NOT NULL,
  currency text NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
  timezone text NOT NULL,
  capabilities jsonb NOT NULL,
  source_document_id text NOT NULL REFERENCES raw.documents,
  UNIQUE (platform, source_shop_id),
  CHECK (shop_key = platform || ':' || source_shop_id),
  FOREIGN KEY (source_document_id, merchant_id) REFERENCES raw.documents(document_id, merchant_id)
);
CREATE INDEX IF NOT EXISTS shops_merchant ON core.shops(merchant_id);
CREATE TABLE IF NOT EXISTS core.products (
  shop_key text NOT NULL REFERENCES core.shops,
  sku text NOT NULL,
  name text NOT NULL,
  unit_cost numeric(18,2) CHECK (unit_cost >= 0),
  cost_basis text NOT NULL,
  source_document_id text NOT NULL REFERENCES raw.documents,
  PRIMARY KEY (shop_key, sku)
);
CREATE TABLE IF NOT EXISTS core.orders (
  shop_key text NOT NULL REFERENCES core.shops,
  order_id text NOT NULL,
  ordered_at timestamptz NOT NULL,
  updated_at timestamptz NOT NULL,
  currency text NOT NULL,
  status text NOT NULL CHECK (status IN ('open','shipped','completed','cancelled','mixed','unknown')),
  original_status text NOT NULL,
  seller_discount numeric(18,2) CHECK (seller_discount >= 0),
  platform_discount numeric(18,2) CHECK (platform_discount >= 0),
  promotion_id text,
  enrichment_source_document_id text NOT NULL REFERENCES raw.documents,
  source_document_id text NOT NULL REFERENCES raw.documents,
  PRIMARY KEY (shop_key, order_id)
);
CREATE TABLE IF NOT EXISTS core.order_items (
  shop_key text NOT NULL,
  order_id text NOT NULL,
  line_id text NOT NULL,
  sku text NOT NULL,
  quantity integer NOT NULL CHECK (quantity > 0),
  unit_price numeric(18,2) NOT NULL CHECK (unit_price >= 0),
  status text NOT NULL CHECK (status IN ('open','shipped','completed','cancelled','unknown')),
  source_document_id text NOT NULL REFERENCES raw.documents,
  PRIMARY KEY (shop_key, order_id, line_id),
  FOREIGN KEY (shop_key, order_id) REFERENCES core.orders,
  FOREIGN KEY (shop_key, sku) REFERENCES core.products
);
CREATE TABLE IF NOT EXISTS core.reviews (
  shop_key text NOT NULL,
  review_id text NOT NULL,
  order_id text NOT NULL,
  sku text NOT NULL,
  reviewed_at timestamptz NOT NULL,
  rating integer NOT NULL CHECK (rating BETWEEN 1 AND 5),
  body text NOT NULL,
  source_document_id text NOT NULL REFERENCES raw.documents,
  PRIMARY KEY (shop_key, review_id),
  FOREIGN KEY (shop_key, order_id) REFERENCES core.orders,
  FOREIGN KEY (shop_key, sku) REFERENCES core.products
);
CREATE TABLE IF NOT EXISTS core.returns (
  shop_key text NOT NULL,
  return_id text NOT NULL,
  order_id text NOT NULL,
  requested_at timestamptz NOT NULL,
  reason text NOT NULL,
  status text NOT NULL,
  refund_amount numeric(18,2) NOT NULL CHECK (refund_amount >= 0),
  source_document_id text NOT NULL REFERENCES raw.documents,
  PRIMARY KEY (shop_key, return_id),
  FOREIGN KEY (shop_key, order_id) REFERENCES core.orders
);
CREATE TABLE IF NOT EXISTS core.inventory (
  shop_key text NOT NULL,
  sku text NOT NULL,
  location_id text NOT NULL,
  observed_at timestamptz NOT NULL,
  available integer CHECK (available >= 0),
  source_document_id text NOT NULL REFERENCES raw.documents,
  PRIMARY KEY (shop_key, sku, location_id, observed_at),
  FOREIGN KEY (shop_key, sku) REFERENCES core.products
);
CREATE TABLE IF NOT EXISTS core.promotions (
  shop_key text NOT NULL REFERENCES core.shops,
  promotion_id text NOT NULL,
  name text NOT NULL,
  funding text NOT NULL CHECK (funding IN ('seller','platform','shared','unknown')),
  starts_at timestamptz NOT NULL,
  ends_at timestamptz NOT NULL CHECK (ends_at > starts_at),
  source_document_id text NOT NULL REFERENCES raw.documents,
  PRIMARY KEY (shop_key, promotion_id)
);
CREATE TABLE IF NOT EXISTS core.settlements (
  shop_key text NOT NULL,
  order_id text NOT NULL,
  fee_amount numeric(18,2) CHECK (fee_amount >= 0),
  seller_shipping_cost numeric(18,2) CHECK (seller_shipping_cost >= 0),
  refund_amount numeric(18,2) CHECK (refund_amount >= 0),
  actual_payout numeric(18,2),
  paid_at timestamptz,
  source_document_id text NOT NULL REFERENCES raw.documents,
  PRIMARY KEY (shop_key, order_id),
  FOREIGN KEY (shop_key, order_id) REFERENCES core.orders
);
CREATE TABLE IF NOT EXISTS core.fulfillment (
  shop_key text NOT NULL,
  order_id text NOT NULL,
  ship_by timestamptz NOT NULL,
  shipped_at timestamptz,
  deadline_basis text NOT NULL,
  source_document_id text NOT NULL REFERENCES raw.documents,
  PRIMARY KEY (shop_key, order_id),
  FOREIGN KEY (shop_key, order_id) REFERENCES core.orders
);
CREATE TABLE IF NOT EXISTS core.account_health (
  shop_key text NOT NULL REFERENCES core.shops,
  event_id text NOT NULL,
  occurred_at timestamptz NOT NULL,
  expires_at timestamptz NOT NULL,
  penalty_points integer NOT NULL CHECK (penalty_points >= 0),
  reason text NOT NULL,
  source_document_id text NOT NULL REFERENCES raw.documents,
  PRIMARY KEY (shop_key, event_id)
);
CREATE INDEX IF NOT EXISTS orders_time ON core.orders(shop_key, ordered_at);
CREATE INDEX IF NOT EXISTS reviews_time ON core.reviews(shop_key, reviewed_at);

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
