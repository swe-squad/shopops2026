CREATE TABLE mock.products (
    shop_key text NOT NULL REFERENCES mock.shops,
    sku text NOT NULL,
    name text NOT NULL,
    unit_cost numeric(18,2) CHECK (unit_cost >= 0),
    cost_basis text NOT NULL,
    deleted_at timestamptz,
    PRIMARY KEY (shop_key, sku)
);
CREATE TABLE mock.promotions (
    shop_key text NOT NULL REFERENCES mock.shops,
    promotion_id text NOT NULL,
    name text NOT NULL,
    funding text NOT NULL CHECK (funding IN ('seller','platform','shared','unknown')),
    starts_at timestamptz NOT NULL,
    ends_at timestamptz NOT NULL CHECK (ends_at > starts_at),
    deleted_at timestamptz,
    PRIMARY KEY (shop_key, promotion_id)
);
