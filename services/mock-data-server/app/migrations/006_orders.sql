CREATE TABLE mock.orders (
  shop_key text NOT NULL REFERENCES mock.shops,
  order_id text NOT NULL,
  ordered_at timestamptz NOT NULL,
  updated_at timestamptz NOT NULL,
  currency text NOT NULL,
  status text NOT NULL CHECK (status IN ('open','shipped','completed','cancelled','mixed','unknown')),
  original_status text NOT NULL,
  seller_discount numeric(18,2) CHECK (seller_discount >= 0),
  platform_discount numeric(18,2) CHECK (platform_discount >= 0),
  promotion_id text,
  deleted_at timestamptz,
  PRIMARY KEY (shop_key, order_id)
);
CREATE TABLE mock.order_items (
  shop_key text NOT NULL,
  order_id text NOT NULL,
  line_id text NOT NULL,
  sku text NOT NULL,
  quantity integer NOT NULL CHECK (quantity > 0),
  unit_price numeric(18,2) NOT NULL CHECK (unit_price >= 0),
  status text NOT NULL CHECK (status IN ('open','shipped','completed','cancelled','unknown')),
  native_status text,
  deleted_at timestamptz,
  PRIMARY KEY (shop_key, order_id, line_id),
  FOREIGN KEY (shop_key, order_id) REFERENCES mock.orders,
  FOREIGN KEY (shop_key, sku) REFERENCES mock.products
);
