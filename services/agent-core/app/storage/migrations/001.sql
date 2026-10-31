BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS orchestrators (
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, shop_id TEXT NOT NULL,
 body TEXT NOT NULL, UNIQUE(tenant_id, shop_id));
CREATE TABLE IF NOT EXISTS config_revisions (
 orchestrator_id TEXT NOT NULL REFERENCES orchestrators(id) ON DELETE CASCADE,
 revision TEXT NOT NULL, body TEXT NOT NULL, PRIMARY KEY(orchestrator_id, revision));
CREATE TRIGGER IF NOT EXISTS immutable_revision BEFORE UPDATE ON config_revisions
 BEGIN SELECT RAISE(ABORT, 'immutable config revision'); END;
CREATE TABLE IF NOT EXISTS conversations (
 id TEXT PRIMARY KEY, orchestrator_id TEXT NOT NULL REFERENCES orchestrators(id),
 config_revision TEXT NOT NULL, tenant_id TEXT NOT NULL, shop_id TEXT NOT NULL,
 user_id TEXT NOT NULL, client_key TEXT NOT NULL, status TEXT NOT NULL,
 provider_session_id TEXT UNIQUE, body TEXT NOT NULL, message_sequence INTEGER NOT NULL DEFAULT 0,
 FOREIGN KEY(orchestrator_id, config_revision) REFERENCES config_revisions(orchestrator_id, revision),
 UNIQUE(tenant_id, shop_id, user_id, client_key));
CREATE TABLE IF NOT EXISTS runs (
 id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
 client_key TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN
 ('queued','running','waiting_tool','reconciling','completed','failed','cancelled')),
 created_at TEXT NOT NULL, body TEXT NOT NULL, event_sequence INTEGER NOT NULL DEFAULT 0, UNIQUE(conversation_id, client_key));
CREATE UNIQUE INDEX IF NOT EXISTS one_nonterminal_run ON runs(conversation_id)
 WHERE state IN ('queued','running','waiting_tool','reconciling');
CREATE INDEX IF NOT EXISTS queue ON runs(state, created_at);
CREATE TABLE IF NOT EXISTS messages (
 id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
 run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
 sequence INTEGER NOT NULL, provider_item_id TEXT, body TEXT NOT NULL,
 UNIQUE(conversation_id, sequence), UNIQUE(conversation_id, provider_item_id));
CREATE TABLE IF NOT EXISTS events (
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
 sequence INTEGER NOT NULL, provider_event_id TEXT, body TEXT NOT NULL,
 UNIQUE(run_id, sequence), UNIQUE(run_id, provider_event_id));
CREATE TABLE IF NOT EXISTS tool_calls (
 run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE, session_id TEXT NOT NULL,
 turn_id TEXT NOT NULL, call_id TEXT NOT NULL, name TEXT NOT NULL, arguments TEXT NOT NULL,
 result TEXT, delivered INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(session_id, turn_id, call_id));
PRAGMA user_version=1;
COMMIT;
