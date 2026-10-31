-- Apply as an operator. Runtime control credentials receive only these objects.
CREATE SCHEMA IF NOT EXISTS mcp_control;
CREATE TABLE IF NOT EXISTS mcp_control.revoked_tokens(jti text PRIMARY KEY);
CREATE TABLE IF NOT EXISTS mcp_control.results (
    id text PRIMARY KEY,
    shop_key text NOT NULL,
    subject text NOT NULL,
    payload jsonb NOT NULL,
    grants text[] NOT NULL,
    expires_at timestamptz NOT NULL,
    bytes bigint NOT NULL CHECK (bytes >= 0)
);
CREATE INDEX IF NOT EXISTS results_scope ON mcp_control.results(shop_key, subject, expires_at);
CREATE TABLE IF NOT EXISTS mcp_control.refreshes (
    shop_key text NOT NULL,
    subject text NOT NULL,
    idempotency_key text NOT NULL,
    body jsonb NOT NULL,
    operation_id text,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(shop_key, subject, idempotency_key)
);
