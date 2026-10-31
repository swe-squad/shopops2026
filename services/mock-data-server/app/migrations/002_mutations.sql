CREATE TABLE mock.receipts (
    actor text NOT NULL,
    idempotency_key text NOT NULL,
    intent_hash text NOT NULL,
    response jsonb NOT NULL,
    PRIMARY KEY (actor, idempotency_key)
);
