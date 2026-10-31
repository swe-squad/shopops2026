CREATE TABLE mock.reviews (
  shop_key text NOT NULL,
  review_id text NOT NULL,
  order_id text NOT NULL,
  sku text NOT NULL,
  reviewed_at timestamptz NOT NULL,
  rating integer NOT NULL CHECK (rating BETWEEN 1 AND 5),
  body text NOT NULL,
  deleted_at timestamptz,
  PRIMARY KEY (shop_key, review_id),
  FOREIGN KEY (shop_key, order_id) REFERENCES mock.orders,
  FOREIGN KEY (shop_key, sku) REFERENCES mock.products
);
CREATE TABLE mock.returns (
  shop_key text NOT NULL,
  return_id text NOT NULL,
  order_id text NOT NULL,
  requested_at timestamptz NOT NULL,
  reason text NOT NULL,
  status text NOT NULL,
  refund_amount numeric(18,2) NOT NULL CHECK (refund_amount >= 0),
  deleted_at timestamptz,
  PRIMARY KEY (shop_key, return_id),
  FOREIGN KEY (shop_key, order_id) REFERENCES mock.orders
);
