CREATE TABLE mock.document_versions (
    shop_key text NOT NULL REFERENCES mock.shops,
    resource text NOT NULL,
    document jsonb NOT NULL,
    PRIMARY KEY (shop_key, resource)
);
