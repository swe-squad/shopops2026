CREATE TABLE sync.state (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    revision bigint NOT NULL DEFAULT -1,
    snapshot_hash text,
    last_run_id uuid
);
INSERT INTO sync.state (singleton) VALUES (true);
CREATE TABLE sync.applied_deletions (
    tombstone_id bigint PRIMARY KEY,
    revision bigint NOT NULL,
    resource text NOT NULL,
    record_key jsonb NOT NULL,
    scope jsonb NOT NULL,
    deleted_at timestamptz NOT NULL
);
