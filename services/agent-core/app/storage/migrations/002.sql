BEGIN IMMEDIATE;
ALTER TABLE runs ADD COLUMN output_mode TEXT NOT NULL DEFAULT 'text'
 CHECK(output_mode IN ('text','report'));
CREATE TABLE runtime_mappings (
 conversation_id TEXT PRIMARY KEY REFERENCES conversations(id) ON DELETE CASCADE,
 environment_id TEXT NOT NULL UNIQUE, body TEXT NOT NULL);
CREATE TABLE artifacts (
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
 conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
 session_id TEXT NOT NULL, turn_id TEXT NOT NULL, provider_id TEXT NOT NULL,
 body TEXT NOT NULL, UNIQUE(session_id,turn_id,provider_id));
CREATE INDEX artifacts_by_run ON artifacts(run_id,id);
PRAGMA user_version=2;
COMMIT;
