CREATE TABLE mock.tombstones (
    tombstone_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    revision bigint NOT NULL,
    resource text NOT NULL,
    record_key jsonb NOT NULL,
    scope jsonb NOT NULL,
    deleted_at timestamptz NOT NULL DEFAULT now()
);
