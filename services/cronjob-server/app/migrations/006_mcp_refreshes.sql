-- MCP request ownership is independent from demo actors and ordinary manual runs.
CREATE TABLE sync.mcp_refreshes (
  subject text NOT NULL,
  shop_key text NOT NULL,
  idempotency_key text NOT NULL,
  request jsonb NOT NULL,
  run_id uuid NOT NULL UNIQUE REFERENCES sync.runs(run_id),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (subject, shop_key, idempotency_key)
);
CREATE INDEX mcp_refreshes_shop_time ON sync.mcp_refreshes(shop_key, created_at);
