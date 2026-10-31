CREATE TABLE mock.shops (
    shop_key text PRIMARY KEY,
    merchant_id text NOT NULL REFERENCES mock.merchants,
    platform text NOT NULL CHECK (platform IN ('shopee-open-platform','lazada','shopify')),
    source_shop_id text NOT NULL,
    name text NOT NULL,
    currency text NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
    timezone text NOT NULL,
    capabilities jsonb NOT NULL,
    deleted_at timestamptz,
    UNIQUE (platform, source_shop_id),
    CHECK (shop_key = platform || ':' || source_shop_id)
);
