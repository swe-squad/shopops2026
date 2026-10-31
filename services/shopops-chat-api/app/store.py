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
