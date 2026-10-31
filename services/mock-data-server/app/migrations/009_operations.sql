CREATE TABLE mock.settlements (
  shop_key text NOT NULL,
  order_id text NOT NULL,
  fee_amount numeric(18,2) CHECK (fee_amount >= 0),
  seller_shipping_cost numeric(18,2) CHECK (seller_shipping_cost >= 0),
  refund_amount numeric(18,2) CHECK (refund_amount >= 0),
  actual_payout numeric(18,2),
  paid_at timestamptz,
  deleted_at timestamptz,
  PRIMARY KEY (shop_key, order_id),
  FOREIGN KEY (shop_key, order_id) REFERENCES mock.orders
);
CREATE TABLE mock.fulfillment (
  shop_key text NOT NULL,
  order_id text NOT NULL,
  ship_by timestamptz NOT NULL,
  shipped_at timestamptz,
  deadline_basis text NOT NULL,
  deleted_at timestamptz,
  PRIMARY KEY (shop_key, order_id),
  FOREIGN KEY (shop_key, order_id) REFERENCES mock.orders
);
CREATE TABLE mock.account_health (
  shop_key text NOT NULL REFERENCES mock.shops,
  event_id text NOT NULL,
  occurred_at timestamptz NOT NULL,
  expires_at timestamptz NOT NULL,
  penalty_points integer NOT NULL CHECK (penalty_points >= 0),
  reason text NOT NULL,
  deleted_at timestamptz,
  PRIMARY KEY (shop_key, event_id)
);
