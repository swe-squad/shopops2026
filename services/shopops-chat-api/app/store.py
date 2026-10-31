import sqlite3
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class BusyError(Exception):
    pass


class Store:
    """A persisted lease serializes this single workspace across server workers."""

    def __init__(self, path: str) -> None:
        self.path = path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=5)
        try:
            db.row_factory = sqlite3.Row
            with db:
                yield db
        finally:
            db.close()

    def initialize(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY, text TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user','assistant')),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS workspace (
                    id INTEGER PRIMARY KEY CHECK(id=1), session_id TEXT
                );
                INSERT OR IGNORE INTO workspace(id) VALUES(1);
                CREATE TABLE IF NOT EXISTS turns (
                    submission_key TEXT PRIMARY KEY, user_message_id INTEGER NOT NULL,
                    session_id TEXT, provider_turn_id TEXT, baseline_turn_id TEXT,
                    status TEXT NOT NULL, owner TEXT, lease_until REAL NOT NULL DEFAULT 0,
                    dispatched INTEGER NOT NULL DEFAULT 0
                );
                CREATE UNIQUE INDEX IF NOT EXISTS one_pending_turn ON turns(status)
                    WHERE status='pending';
            """)

    def ensure_legacy(self) -> None:
        with self.connect() as db:
            exists = db.execute("SELECT 1 FROM sqlite_master WHERE name='core_outbox'").fetchone()
            if exists and db.execute("SELECT 1 FROM core_outbox WHERE status='pending'").fetchone():
                raise RuntimeError("Resolve pending Core work before switching backend")

    def history(self) -> list[dict]:
        with self.connect() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM (SELECT * FROM messages ORDER BY id DESC LIMIT 100) ORDER BY id"
                )
            ]

    def claim(self, text: str | None, owner: str) -> dict | None:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM turns WHERE status='pending'").fetchone()
            if row:
                if row["owner"] and row["lease_until"] > time.time():
                    raise BusyError("A chat turn is already running. Wait before sending again.")
                db.execute(
                    "UPDATE turns SET owner=?, lease_until=? WHERE submission_key=?",
                    (owner, time.time() + 90, row["submission_key"]),
                )
                return dict(row) | {"owner": owner, "recover": True}
            if text is None:
                return None
            cursor = db.execute("INSERT INTO messages(text,role) VALUES(?,'user')", (text,))
            session_id = db.execute("SELECT session_id FROM workspace").fetchone()[0]
            key = str(uuid.uuid4())
            db.execute(
                "INSERT INTO turns(submission_key,user_message_id,session_id,status,owner,"
                "lease_until) VALUES(?,?,?,'pending',?,?)",
                (key, cursor.lastrowid, session_id, owner, time.time() + 90),
            )
            return dict(db.execute("SELECT * FROM turns WHERE submission_key=?", (key,)).fetchone())

    def update(self, key: str, owner: str, **values: str | int) -> None:
        allowed = {"session_id", "provider_turn_id", "baseline_turn_id", "dispatched"}
        if not values or not set(values) <= allowed:
            raise ValueError("Invalid turn update")
        with self.connect() as db:
            assignments = ",".join(f"{name}=?" for name in values)
            result = db.execute(
                f"UPDATE turns SET {assignments} WHERE submission_key=? AND owner=?",
                (*values.values(), key, owner),
            )
            if result.rowcount != 1:
                raise BusyError("The chat turn lease was lost.")
            if "session_id" in values:
                db.execute("UPDATE workspace SET session_id=?", (values["session_id"],))

    def heartbeat(self, key: str, owner: str) -> None:
        with self.connect() as db:
            result = db.execute(
                "UPDATE turns SET lease_until=? WHERE submission_key=? AND owner=?",
                (time.time() + 90, key, owner),
            )
            if result.rowcount != 1:
                raise BusyError("The chat turn lease was lost.")

    def release(self, key: str, owner: str) -> None:
        with self.connect() as db:
            db.execute(
                "UPDATE turns SET owner=NULL,lease_until=0 WHERE submission_key=? AND owner=?",
                (key, owner),
            )

    def finish(self, key: str, owner: str, text: str | None) -> dict | None:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            result = db.execute(
                "UPDATE turns SET status=?,owner=NULL,lease_until=0 "
                "WHERE submission_key=? AND owner=? AND status='pending'",
                ("completed" if text is not None else "failed", key, owner),
            )
            if result.rowcount != 1:
                raise BusyError("The chat turn lease was lost.")
            if text is None:
                return None
            cursor = db.execute("INSERT INTO messages(text,role) VALUES(?,'assistant')", (text,))
            return dict(
                db.execute("SELECT * FROM messages WHERE id=?", (cursor.lastrowid,)).fetchone()
            )


class CoreStore(Store):
    def initialize(self) -> None:
        super().initialize()
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS demo_sessions (
                    token_hash TEXT PRIMARY KEY, identity TEXT NOT NULL, expires REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS core_spaces (
                    namespace TEXT PRIMARY KEY, actor TEXT NOT NULL, configuration TEXT NOT NULL,
                    client_id TEXT NOT NULL, orchestrator TEXT, conversation TEXT
                );
                CREATE TABLE IF NOT EXISTS core_outbox (
                    namespace TEXT NOT NULL, client_id TEXT NOT NULL, payload TEXT NOT NULL,
                    run_id TEXT, message_id TEXT, status TEXT NOT NULL DEFAULT 'pending',
                    owner TEXT, lease REAL NOT NULL DEFAULT 0,
                    message_dispatched INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(namespace,client_id)
                );
                CREATE UNIQUE INDEX IF NOT EXISTS core_one_pending ON core_outbox(namespace)
                    WHERE status='pending';
                CREATE TABLE IF NOT EXISTS core_artifacts (
                    namespace TEXT NOT NULL, id TEXT NOT NULL, run_id TEXT NOT NULL,
                    metadata TEXT NOT NULL, PRIMARY KEY(namespace,id)
                );
            """)

            db.execute("BEGIN IMMEDIATE")
            columns = {row["name"] for row in db.execute("PRAGMA table_info(core_outbox)")}
            if "message_dispatched" not in columns:
                # Older rows lack evidence of whether their message POST reached Core.
                db.execute(
                    "ALTER TABLE core_outbox ADD COLUMN"
                    " message_dispatched INTEGER NOT NULL DEFAULT 1"
                )

    def space(self, namespace: str, actor: str, configuration: str) -> dict:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM turns WHERE status='pending'").fetchone():
                raise BusyError("Resolve the previous workspace turn before switching backend.")
            if db.execute(
                "SELECT 1 FROM core_outbox o JOIN core_spaces s USING(namespace) "
                "WHERE o.status='pending' AND s.actor=? AND s.configuration!=?",
                (actor, configuration),
            ).fetchone():
                raise BusyError("Resolve the previous configuration before switching.")
            db.execute(
                "INSERT OR IGNORE INTO core_spaces VALUES(?,?,?,?,NULL,NULL)",
                (namespace, actor, configuration, str(uuid.uuid4())),
            )
            return dict(
                db.execute("SELECT * FROM core_spaces WHERE namespace=?", (namespace,)).fetchone()
            )

    def core_claim(
        self, namespace: str, key: str | None, payload: str | None, owner: str
    ) -> dict | None:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = (
                db.execute(
                    "SELECT * FROM core_outbox WHERE namespace=? AND client_id=?", (namespace, key)
                ).fetchone()
                if key
                else None
            )
            if existing and existing["payload"] != payload:
                raise ValueError("Idempotency conflict")
            row = (
                existing
                or db.execute(
                    "SELECT * FROM core_outbox WHERE namespace=? AND status='pending'", (namespace,)
                ).fetchone()
            )
            if row:
                if row["status"] != "pending":
                    return dict(row)
                if key and row["client_id"] != key:
                    raise BusyError("Load history before sending another turn.")
                if row["owner"] and row["lease"] > time.time():
                    raise BusyError("A turn is already being inspected.")
            elif key:
                db.execute(
                    "INSERT INTO core_outbox(namespace,client_id,payload,message_dispatched)"
                    " VALUES(?,?,?,0)",
                    (namespace, key, payload),
                )
                row = db.execute(
                    "SELECT * FROM core_outbox WHERE namespace=? AND client_id=?", (namespace, key)
                ).fetchone()
            else:
                return None
            db.execute(
                "UPDATE core_outbox SET owner=?,lease=? WHERE namespace=? AND client_id=?",
                (owner, time.time() + 30, namespace, row["client_id"]),
            )
            return dict(row) | {"owner": owner}

    def core_update(self, namespace: str, key: str, owner: str, **values) -> None:
        if not set(values) <= {"run_id", "message_id", "status", "message_dispatched"}:
            raise ValueError("Invalid update")
        with self.connect() as db:
            result = db.execute(
                "UPDATE core_outbox SET lease=?"
                + "".join(f", {k}=?" for k in values)
                + " WHERE namespace=? AND client_id=? AND owner=?"
                " AND lease>?",
                (time.time() + 30, *values.values(), namespace, key, owner, time.time()),
            )
            if result.rowcount != 1:
                raise BusyError("Turn lease was lost.")

    def core_release(self, namespace: str, key: str, owner: str) -> None:
        with self.connect() as db:
            db.execute(
                "UPDATE core_outbox SET owner=NULL,lease=0"
                " WHERE namespace=? AND client_id=? AND owner=?",
                (namespace, key, owner),
            )

    def core_space_update(self, namespace: str, **values) -> None:
        if not set(values) <= {"orchestrator", "conversation"}:
            raise ValueError("Invalid space update")
        with self.connect() as db:
            db.execute(
                "UPDATE core_spaces SET "
                + ",".join(f"{k}=?" for k in values)
                + " WHERE namespace=?",
                (*values.values(), namespace),
            )

    def core_save_artifacts(self, namespace: str, run_id: str, artifacts: list[dict]) -> None:
        import json

        with self.connect() as db:
            for artifact in artifacts:
                db.execute(
                    "INSERT OR REPLACE INTO core_artifacts VALUES(?,?,?,?)",
                    (namespace, artifact["id"], run_id, json.dumps(artifact)),
                )

    def core_artifact(self, namespace: str, artifact_id: str) -> dict | None:
        import json

        with self.connect() as db:
            row = db.execute(
                "SELECT metadata FROM core_artifacts WHERE namespace=? AND id=?",
                (namespace, artifact_id),
            ).fetchone()
            return json.loads(row[0]) if row else None

    def core_output_mode(self, namespace: str, run_id: str) -> str:
        import json

        with self.connect() as db:
            row = db.execute(
                "SELECT payload FROM core_outbox WHERE namespace=? AND run_id=?",
                (namespace, run_id),
            ).fetchone()
            return json.loads(row[0])["output_mode"] if row else "text"
