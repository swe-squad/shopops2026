CREATE TABLE mock.inventory (
  shop_key text NOT NULL,
  sku text NOT NULL,
  location_id text NOT NULL,
  observed_at timestamptz NOT NULL,
  available integer CHECK (available >= 0),
  deleted_at timestamptz,
  PRIMARY KEY (shop_key, sku, location_id, observed_at),
  FOREIGN KEY (shop_key, sku) REFERENCES mock.products
);
