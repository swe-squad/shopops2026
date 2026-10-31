CREATE TABLE sync.runs (
    run_id uuid PRIMARY KEY,
    actor text NOT NULL,
    idempotency_key text NOT NULL,
    intent_hash text NOT NULL,
    trigger text NOT NULL CHECK (trigger IN ('manual','mutation','interval')),
    status text NOT NULL CHECK (status IN ('pending_mutation','queued','running','succeeded','failed')),
    created_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    finished_at timestamptz,
    attempts integer NOT NULL DEFAULT 0,
    minimum_revision bigint NOT NULL DEFAULT 0,
    applied_revision bigint,
    result jsonb,
    error_stage text,
    error_code text,
    UNIQUE(actor, idempotency_key)
);
CREATE TABLE sync.mutation_intents (
    run_id uuid PRIMARY KEY REFERENCES sync.runs,
    request jsonb NOT NULL,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','applied','rejected','unknown')),
    response jsonb,
    rejection_status integer,
    attempts integer NOT NULL DEFAULT 0
);
CREATE INDEX runs_pending ON sync.runs(created_at) WHERE status IN ('pending_mutation','queued','running');
CREATE TABLE sync.settings_receipts (
    idempotency_key text PRIMARY KEY,
    intent_hash text NOT NULL,
    response jsonb NOT NULL
);
