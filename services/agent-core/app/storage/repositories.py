import hashlib
import json
import sqlite3
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import uuid4

from app.config.registry import Registry
from app.contracts.errors import (
    ConfigurationConflict,
    ConversationBusy,
    IdempotencyConflict,
    InvalidCursor,
    InvalidInput,
    InvalidOutput,
    InvalidTransition,
    NotFound,
)
from app.contracts.identity import Scope
from app.contracts.models import (
    TERMINAL,
    ApplicationResponse,
    ConfigSnapshot,
    Conversation,
    EnqueueResult,
    IdempotentResult,
    Message,
    MessageReceipt,
    Orchestrator,
    Page,
    Run,
    RunEvent,
    RunState,
    Source,
)
from app.contracts.runtime import ArtifactRecord, ProviderEnvironment
from app.contracts.tools import PendingToolCall, ToolResult
from app.runs.state import TRANSITIONS
from app.storage.database import Database


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid4())


class SQLiteRepository:
    def __init__(
        self,
        database: Database,
        registry: Registry,
        *,
        clock: Callable[[], datetime] = utcnow,
        run_timeout: int = 180,
        recovery_timeout: int = 60,
        max_concurrent: int = 4,
    ) -> None:
        self.database = database
        self.registry = registry
        self.clock = clock
        self.run_timeout = run_timeout
        self.recovery_timeout = recovery_timeout
        self.max_concurrent = max_concurrent

    @staticmethod
    def _conversation(
        db: sqlite3.Connection, conversation_id: str, scope: Scope | None = None
    ) -> Conversation:
        row = db.execute("SELECT body FROM conversations WHERE id=?", (conversation_id,)).fetchone()
        if row is None:
            raise NotFound()
        result = Conversation.model_validate_json(row[0])
        if scope is not None and (
            result.scope.tenant_id,
            result.scope.shop_id,
            result.scope.user_id,
        ) != (scope.tenant_id, scope.shop_id, scope.user_id):
            raise NotFound()
        return result

    @staticmethod
    def _run(db: sqlite3.Connection, run_id: str) -> Run:
        row = db.execute("SELECT body FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise NotFound()
        return Run.model_validate_json(row[0])

    @staticmethod
    def _save_run(db: sqlite3.Connection, run: Run) -> None:
        db.execute(
            "UPDATE runs SET state=?, body=? WHERE id=?", (run.state, run.model_dump_json(), run.id)
        )

    @staticmethod
    def _save_conversation(db: sqlite3.Connection, c: Conversation) -> None:
        db.execute(
            "UPDATE conversations SET status=?,provider_session_id=?,body=? WHERE id=?",
            (c.status, c.provider_session_id, c.model_dump_json(), c.id),
        )

    def _event(
        self,
        db: sqlite3.Connection,
        run_id: str,
        event_type: str,
        *,
        provider_event_id: str | None = None,
        tool_name: str | None = None,
        error: str | None = None,
    ) -> None:
        if (
            provider_event_id is not None
            and db.execute(
                "SELECT 1 FROM events WHERE run_id=? AND provider_event_id=?",
                (run_id, provider_event_id),
            ).fetchone()
        ):
            return
        seq = db.execute(
            "UPDATE runs SET event_sequence=event_sequence+1 WHERE id=? RETURNING event_sequence",
            (run_id,),
        ).fetchone()
        if seq is None:
            raise NotFound()
        event = RunEvent(
            id=new_id(),
            run_id=run_id,
            sequence=seq[0],
            type=event_type,
            tool_name=tool_name,
            error=error,
            provider_event_id=provider_event_id,
            created_at=self.clock(),
        )
        db.execute(
            "INSERT INTO events VALUES(?,?,?,?,?)",
            (event.id, run_id, event.sequence, provider_event_id, event.model_dump_json()),
        )

    def _message(
        self, db: sqlite3.Connection, run: Run, role: str, content: str, item_id: str | None = None
    ) -> Message:
        seq = db.execute(
            "UPDATE conversations SET message_sequence=message_sequence+1 WHERE id=? "
            "RETURNING message_sequence",
            (run.conversation_id,),
        ).fetchone()[0]
        message = Message(
            id=new_id(),
            conversation_id=run.conversation_id,
            run_id=run.id,
            role=role,
            content=content,
            sequence=seq,
            provider_item_id=item_id,
            created_at=self.clock(),
        )
        db.execute(
            "INSERT INTO messages VALUES(?,?,?,?,?,?)",
            (message.id, run.conversation_id, run.id, seq, item_id, message.model_dump_json()),
        )
        return message

    def _revision(self, db: sqlite3.Connection, o: Orchestrator, config: ConfigSnapshot) -> None:
        row = db.execute(
            "SELECT body FROM config_revisions WHERE orchestrator_id=? AND revision=?",
            (o.id, config.revision),
        ).fetchone()
        if row is not None and ConfigSnapshot.model_validate_json(row[0]) != config:
            raise ConfigurationConflict()
        db.execute(
            "INSERT OR IGNORE INTO config_revisions VALUES(?,?,?)",
            (o.id, config.revision, config.model_dump_json()),
        )

    async def provision(
        self, scope: Scope, template_id: str, config_revision: str
    ) -> IdempotentResult[Orchestrator]:
        config = self.registry.get(template_id, config_revision)

        def operation(db: sqlite3.Connection) -> IdempotentResult[Orchestrator]:
            row = db.execute(
                "SELECT body FROM orchestrators WHERE tenant_id=? AND shop_id=?",
                (scope.tenant_id, scope.shop_id),
            ).fetchone()
            if row is not None:
                o = Orchestrator.model_validate_json(row[0])
                if o.config_revision != config_revision or o.template_id != template_id:
                    raise ConfigurationConflict()
                self._revision(db, o, config)
                return IdempotentResult(record=o, created=False)
            o = Orchestrator(
                id=new_id(),
                tenant_id=scope.tenant_id,
                shop_id=scope.shop_id,
                config_revision=config_revision,
                template_id=template_id,
            )
            db.execute(
                "INSERT INTO orchestrators VALUES(?,?,?,?)",
                (o.id, o.tenant_id, o.shop_id, o.model_dump_json()),
            )
            self._revision(db, o, config)
            return IdempotentResult(record=o, created=True)

        return await self.database.transaction(operation)

    async def activate_revision(self, scope: Scope, template_id: str, revision: str) -> None:
        config = self.registry.get(template_id, revision)

        def operation(db: sqlite3.Connection) -> None:
            row = db.execute(
                "SELECT body FROM orchestrators WHERE tenant_id=? AND shop_id=?",
                (scope.tenant_id, scope.shop_id),
            ).fetchone()
            if row is None:
                raise NotFound()
            o = Orchestrator.model_validate_json(row[0])
            if o.template_id != template_id:
                raise ConfigurationConflict()
            self._revision(db, o, config)
            o = o.model_copy(update={"config_revision": revision})
            db.execute("UPDATE orchestrators SET body=? WHERE id=?", (o.model_dump_json(), o.id))

        await self.database.transaction(operation)

    async def create_conversation(
        self, scope: Scope, orchestrator_id: str, client_conversation_id: str
    ) -> IdempotentResult[Conversation]:
        if not 1 <= len(client_conversation_id) <= 128:
            raise InvalidInput()

        def operation(db: sqlite3.Connection) -> IdempotentResult[Conversation]:
            row = db.execute(
                "SELECT body FROM conversations WHERE tenant_id=? AND shop_id=? "
                "AND user_id=? AND client_key=?",
                (scope.tenant_id, scope.shop_id, scope.user_id, client_conversation_id),
            ).fetchone()
            if row is not None:
                c = Conversation.model_validate_json(row[0])
                if c.orchestrator_id != orchestrator_id:
                    raise IdempotencyConflict()
                return IdempotentResult(record=c, created=False)
            row = db.execute(
                "SELECT body FROM orchestrators WHERE id=? AND tenant_id=? AND shop_id=?",
                (orchestrator_id, scope.tenant_id, scope.shop_id),
            ).fetchone()
            if row is None:
                raise NotFound()
            o = Orchestrator.model_validate_json(row[0])
            config = ConfigSnapshot.model_validate_json(
                db.execute(
                    "SELECT body FROM config_revisions WHERE orchestrator_id=? AND revision=?",
                    (o.id, o.config_revision),
                ).fetchone()[0]
            )
            c = Conversation(
                id=new_id(),
                scope=scope,
                orchestrator_id=o.id,
                config=config,
                client_conversation_id=client_conversation_id,
                created_at=self.clock(),
            )
            db.execute(
                "INSERT INTO conversations(id,orchestrator_id,config_revision,tenant_id,shop_id,"
                "user_id,client_key,status,provider_session_id,body) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    c.id,
                    o.id,
                    config.revision,
                    scope.tenant_id,
                    scope.shop_id,
                    scope.user_id,
                    client_conversation_id,
                    c.status,
                    None,
                    c.model_dump_json(),
                ),
            )
            return IdempotentResult(record=c, created=True)

        return await self.database.transaction(operation)

    async def enqueue_message(
        self,
        scope: Scope,
        conversation_id: str,
        client_message_id: str,
        content: str,
        *,
        output_mode: Literal["text", "report"] = "text",
    ) -> EnqueueResult:
        content = content.strip()
        if not 1 <= len(content) <= 8000 or not 1 <= len(client_message_id) <= 128:
            raise InvalidInput()
        if output_mode not in ("text", "report"):
            raise InvalidInput()
        digest = hashlib.sha256(
            (content if output_mode == "text" else "report\0" + content).encode()
        ).hexdigest()

        def operation(db: sqlite3.Connection) -> EnqueueResult:
            c = self._conversation(db, conversation_id, scope)
            row = db.execute(
                "SELECT body FROM runs WHERE conversation_id=? AND client_key=?",
                (conversation_id, client_message_id),
            ).fetchone()
            if row is not None:
                run = Run.model_validate_json(row[0])
                if run.request_hash != digest or run.output_mode != output_mode:
                    raise IdempotencyConflict()
                message_row = db.execute(
                    "SELECT body FROM messages WHERE run_id=? AND provider_item_id IS NULL",
                    (run.id,),
                ).fetchone()
                if message_row is not None:
                    message = Message.model_validate_json(message_row[0])
                elif run.message_receipt is not None:
                    receipt = run.message_receipt
                    message = Message(
                        id=receipt.id,
                        conversation_id=conversation_id,
                        run_id=run.id,
                        role="user",
                        content=content,
                        sequence=receipt.sequence,
                        created_at=receipt.created_at,
                    )
                else:
                    raise IdempotencyConflict()  # legacy run without retained receipt
                return EnqueueResult(message=message, run=run, created=False)
            busy = db.execute(
                "SELECT 1 FROM runs WHERE conversation_id=? AND state IN "
                "('queued','running','waiting_tool','reconciling')",
                (conversation_id,),
            ).fetchone()
            if c.status != "active" or busy:
                raise ConversationBusy()
            if output_mode == "report" and c.config.runtime_profile.environment_type == "none":
                raise InvalidInput()
            now = self.clock()
            run = Run(
                output_mode=output_mode,
                id=new_id(),
                conversation_id=conversation_id,
                client_message_id=client_message_id,
                request_hash=digest,
                scope=scope,
                state="queued",
                deadline=now + timedelta(seconds=self.run_timeout),
                recovery_deadline=now + timedelta(seconds=self.run_timeout + self.recovery_timeout),
                config=c.config,
                created_at=now,
            )
            db.execute(
                "INSERT INTO runs(id,conversation_id,client_key,state,created_at,body,output_mode) "
                "VALUES(?,?,?,?,?,?,?)",
                (
                    run.id,
                    conversation_id,
                    client_message_id,
                    run.state,
                    now.isoformat(),
                    run.model_dump_json(),
                    output_mode,
                ),
            )
            message = self._message(db, run, "user", content)
            run = run.model_copy(
                update={
                    "message_receipt": MessageReceipt(
                        id=message.id, sequence=message.sequence, created_at=message.created_at
                    )
                }
            )
            self._save_run(db, run)
            self._event(db, run.id, "run.queued")
            return EnqueueResult(message=message, run=run, created=True)

        return await self.database.transaction(operation)

    async def get_conversation(self, scope: Scope, conversation_id: str) -> Conversation:
        return await self.database.transaction(
            lambda db: self._conversation(db, conversation_id, scope)
        )

    async def get_run(self, scope: Scope, run_id: str) -> Run:
        def operation(db: sqlite3.Connection) -> Run:
            run = self._run(db, run_id)
            self._conversation(db, run.conversation_id, scope)
            return run

        return await self.database.transaction(operation)

    async def get_config_snapshot(self, scope: Scope, conversation_id: str) -> ConfigSnapshot:
        return (await self.get_conversation(scope, conversation_id)).config

    async def _page(
        self, scope: Scope, resource_id: str, after: str | None, limit: int, *, events: bool
    ) -> Page:
        if not 1 <= limit <= 100:
            raise InvalidInput()

        def operation(db: sqlite3.Connection) -> Page:
            if events:
                self._conversation(db, self._run(db, resource_id).conversation_id, scope)
                table, key, model = "events", "run_id", RunEvent
            else:
                self._conversation(db, resource_id, scope)
                table, key, model = "messages", "conversation_id", Message
            sequence = 0
            if after is not None:
                row = db.execute(
                    f"SELECT sequence FROM {table} WHERE id=? AND {key}=?", (after, resource_id)
                ).fetchone()
                if row is None:
                    raise InvalidCursor()
                sequence = row[0]
            rows = db.execute(
                f"SELECT id,body FROM {table} WHERE {key}=? AND sequence>? "
                "ORDER BY sequence LIMIT ?",
                (resource_id, sequence, limit + 1),
            ).fetchall()
            items = tuple(model.model_validate_json(r["body"]) for r in rows[:limit])
            cursor = rows[limit - 1]["id"] if len(rows) > limit else None
            return Page(items=items, next_cursor=cursor)

        return await self.database.transaction(operation)

    async def get_history(
        self, scope: Scope, conversation_id: str, after: str | None = None, limit: int = 50
    ) -> Page[Message]:
        return await self._page(scope, conversation_id, after, limit, events=False)

    async def get_events(
        self, scope: Scope, run_id: str, after: str | None = None, limit: int = 50
    ) -> Page[RunEvent]:
        return await self._page(scope, run_id, after, limit, events=True)

    async def claim_next_run(self) -> Run | None:
        def operation(db: sqlite3.Connection) -> Run | None:
            count = db.execute(
                "SELECT COUNT(*) FROM runs WHERE state IN ('running','waiting_tool')"
            ).fetchone()[0]
            if count >= self.max_concurrent:
                return None
            row = db.execute(
                "SELECT body FROM runs WHERE state='queued' ORDER BY created_at,id LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            run = Run.model_validate_json(row[0]).model_copy(update={"state": "running"})
            self._save_run(db, run)
            self._event(db, run.id, "run.started")
            return run

        return await self.database.transaction(operation)

    async def pending_runs(self) -> tuple[Run, ...]:
        return await self.database.transaction(
            lambda db: tuple(
                Run.model_validate_json(r[0])
                for r in db.execute(
                    "SELECT body FROM runs WHERE state IN ('running','waiting_tool','reconciling')"
                ).fetchall()
            )
        )

    async def recover_interrupted(self) -> None:
        def operation(db: sqlite3.Connection) -> None:
            for row in db.execute(
                "SELECT body FROM runs WHERE state IN ('running','waiting_tool')"
            ).fetchall():
                run = Run.model_validate_json(row[0])
                state = "queued" if run.submission_marker == "none" else "reconciling"
                self._save_run(db, run.model_copy(update={"state": state}))
                self._event(db, run.id, f"run.{state}")

        await self.database.transaction(operation)

    async def execution_context(self, run_id: str) -> tuple[Conversation, Message]:
        def operation(db: sqlite3.Connection) -> tuple[Conversation, Message]:
            run = self._run(db, run_id)
            c = self._conversation(db, run.conversation_id)
            row = db.execute(
                "SELECT body FROM messages WHERE run_id=? AND provider_item_id IS NULL", (run_id,)
            ).fetchone()
            if row is None:
                raise NotFound()
            if run.scope is not None:
                c = c.model_copy(update={"scope": run.scope})
            return c, Message.model_validate_json(row[0])

        return await self.database.transaction(operation)

    async def save_session_mapping(
        self, run_id: str, session_id: str, *, input_submitted: bool = False
    ) -> None:
        def operation(db: sqlite3.Connection) -> None:
            c = self._conversation(db, self._run(db, run_id).conversation_id)
            if c.provider_session_id not in (None, session_id):
                raise IdempotencyConflict()
            self._save_conversation(db, c.model_copy(update={"provider_session_id": session_id}))
            if input_submitted:
                run = self._run(db, run_id)
                self._save_run(db, run.model_copy(update={"submission_marker": "submitted"}))

        await self.database.transaction(operation)

    async def mark_submission(self, run_id: str, marker: str, turn_id: str | None = None) -> None:
        if marker not in ("none", "session_creating", "submitting", "submitted"):
            raise InvalidInput()

        def operation(db: sqlite3.Connection) -> None:
            run = self._run(db, run_id)
            if run.state in TERMINAL:
                raise InvalidTransition()
            self._save_run(
                db,
                run.model_copy(
                    update={
                        "submission_marker": marker,
                        "runtime_setup_started_at": (run.runtime_setup_started_at or self.clock())
                        if marker == "session_creating"
                        else run.runtime_setup_started_at,
                        "provider_turn_id": turn_id or run.provider_turn_id,
                    }
                ),
            )

        await self.database.transaction(operation)

    async def transition_run(
        self,
        run_id: str,
        expected: tuple[RunState, ...],
        target: RunState,
        *,
        error: str | None = None,
        block: bool = False,
    ) -> bool:
        def operation(db: sqlite3.Connection) -> bool:
            run = self._run(db, run_id)
            if run.state not in expected:
                return False
            if target not in TRANSITIONS[run.state]:
                raise InvalidTransition()
            self._save_run(db, run.model_copy(update={"state": target, "error": error}))
            if block:
                c = self._conversation(db, run.conversation_id)
                self._save_conversation(db, c.model_copy(update={"status": "blocked"}))
            self._event(db, run.id, f"run.{target}", error=error)
            return True

        return await self.database.transaction(operation)

    async def append_event(
        self,
        run_id: str,
        event_type: str,
        *,
        provider_event_id: str | None = None,
        tool_name: str | None = None,
        error: str | None = None,
    ) -> None:
        await self.database.transaction(
            lambda db: self._event(
                db,
                run_id,
                event_type,
                provider_event_id=provider_event_id,
                tool_name=tool_name,
                error=error,
            )
        )

    def _tool_row(
        self, db: sqlite3.Connection, run_id: str, call: PendingToolCall
    ) -> sqlite3.Row | None:
        run = self._run(db, run_id)
        c = self._conversation(db, run.conversation_id)
        if c.provider_session_id != call.session_id or run.provider_turn_id != call.turn_id:
            raise IdempotencyConflict()
        row = db.execute(
            "SELECT * FROM tool_calls WHERE session_id=? AND turn_id=? AND call_id=?",
            (call.session_id, call.turn_id, call.call_id),
        ).fetchone()
        if row is not None and (
            row["run_id"] != run_id
            or row["name"] != call.name
            or row["arguments"] != json.dumps(call.arguments, sort_keys=True)
        ):
            raise IdempotencyConflict()
        return row

    async def get_tool_result(
        self, run_id: str, call: PendingToolCall
    ) -> tuple[ToolResult, bool] | None:
        def operation(db: sqlite3.Connection) -> tuple[ToolResult, bool] | None:
            row = self._tool_row(db, run_id, call)
            if row is None or row["result"] is None:
                return None
            return ToolResult.model_validate_json(row["result"]), bool(row["delivered"])

        return await self.database.transaction(operation)

    async def begin_tool_call(self, run_id: str, call: PendingToolCall, maximum: int) -> bool:
        def operation(db: sqlite3.Connection) -> bool:
            row = self._tool_row(db, run_id, call)
            if row is not None:
                return True
            count = db.execute(
                "SELECT COUNT(*) FROM tool_calls WHERE run_id=?", (run_id,)
            ).fetchone()[0]
            if count >= maximum:
                return False
            db.execute(
                "INSERT INTO tool_calls(run_id,session_id,turn_id,call_id,name,arguments) "
                "VALUES(?,?,?,?,?,?)",
                (
                    run_id,
                    call.session_id,
                    call.turn_id,
                    call.call_id,
                    call.name,
                    json.dumps(call.arguments, sort_keys=True),
                ),
            )
            self._event(db, run_id, "tool.started", tool_name=call.name)
            return True

        return await self.database.transaction(operation)

    async def record_tool_result(
        self, run_id: str, call: PendingToolCall, result: ToolResult
    ) -> ToolResult:
        if len(result.model_dump_json().encode()) > 32768:
            raise InvalidOutput()

        def operation(db: sqlite3.Connection) -> ToolResult:
            row = self._tool_row(db, run_id, call)
            if row is None:
                raise InvalidTransition()
            if row["result"] is not None:
                return ToolResult.model_validate_json(row["result"])
            db.execute(
                "UPDATE tool_calls SET result=? WHERE session_id=? AND turn_id=? AND call_id=?",
                (result.model_dump_json(), call.session_id, call.turn_id, call.call_id),
            )
            self._event(
                db,
                run_id,
                "tool.failed" if result.error else "tool.completed",
                tool_name=call.name,
                error=result.error,
            )
            return result

        return await self.database.transaction(operation)

    async def mark_tool_delivered(self, run_id: str, call: PendingToolCall) -> None:
        def operation(db: sqlite3.Connection) -> None:
            row = self._tool_row(db, run_id, call)
            if row is None or row["result"] is None:
                raise InvalidTransition()
            db.execute(
                "UPDATE tool_calls SET delivered=1 WHERE session_id=? AND turn_id=? AND call_id=?",
                (call.session_id, call.turn_id, call.call_id),
            )

        await self.database.transaction(operation)

    async def complete_run(
        self, run_id: str, turn_id: str, item_id: str, response: ApplicationResponse
    ) -> None:
        def operation(db: sqlite3.Connection) -> None:
            run = self._run(db, run_id)
            if run.state in TERMINAL:
                return
            if run.provider_turn_id != turn_id or run.state == "queued":
                raise InvalidTransition()
            sources = set()
            for row in db.execute(
                "SELECT result FROM tool_calls WHERE run_id=? AND result IS NOT NULL", (run_id,)
            ).fetchall():
                result = ToolResult.model_validate_json(row[0])
                if result.error is None:
                    sources.update((s.type, s.reference) for s in result.sources)
            if any((s.type, s.reference) not in sources for s in response.sources):
                raise InvalidOutput()
            duplicate = db.execute(
                "SELECT 1 FROM messages WHERE conversation_id=? AND provider_item_id=?",
                (run.conversation_id, item_id),
            ).fetchone()
            if duplicate:
                raise InvalidOutput()
            self._message(db, run, "assistant", response.text, item_id)
            self._save_run(db, run.model_copy(update={"state": "completed", "response": response}))
            self._event(db, run_id, "run.completed")

        await self.database.transaction(operation)

    async def delete_conversation(
        self, scope: Scope, conversation_id: str, delete_session: Callable[[str], Awaitable[None]]
    ) -> None:
        def mark(db: sqlite3.Connection) -> Conversation:
            c = self._conversation(db, conversation_id, scope)
            if db.execute(
                "SELECT 1 FROM runs WHERE conversation_id=? AND state IN "
                "('queued','running','waiting_tool','reconciling')",
                (conversation_id,),
            ).fetchone():
                raise ConversationBusy()
            self._save_conversation(db, c.model_copy(update={"status": "deleting"}))
            return c

        c = await self.database.transaction(mark)
        try:
            if c.provider_session_id is not None:
                await delete_session(c.provider_session_id)
        except BaseException:
            await self.database.transaction(
                lambda db: self._save_conversation(
                    db, c.model_copy(update={"status": "cleanup_failed"})
                )
            )
            raise
        await self.database.transaction(
            lambda db: db.execute("DELETE FROM conversations WHERE id=?", (conversation_id,))
        )

    async def prune(self, before: str) -> tuple[int, int]:
        cutoff = datetime.fromisoformat(before)
        if cutoff.tzinfo is None:
            raise InvalidInput()

        def operation(db: sqlite3.Connection) -> tuple[int, int]:
            counts = []
            for table in ("messages", "events"):
                rows = db.execute(
                    f"SELECT a.id,a.body FROM {table} a JOIN runs r ON r.id=a.run_id "
                    "WHERE r.state IN ('completed','failed','cancelled')"
                ).fetchall()
                ids = [
                    r[0]
                    for r in rows
                    if datetime.fromisoformat(json.loads(r[1])["created_at"]) < cutoff
                ]
                db.executemany(f"DELETE FROM {table} WHERE id=?", ((i,) for i in ids))
                counts.append(len(ids))
            return counts[0], counts[1]

        return await self.database.transaction(operation)

    async def load_sources(self, session_id: str, turn_id: str) -> tuple[Source, ...]:
        def operation(db: sqlite3.Connection) -> tuple[Source, ...]:
            rows = db.execute(
                "SELECT result FROM tool_calls WHERE session_id=? AND turn_id=? "
                "AND result IS NOT NULL",
                (session_id, turn_id),
            ).fetchall()
            sources = {}
            for row in rows:
                result = ToolResult.model_validate_json(row[0])
                if result.error is None:
                    for source in result.sources:
                        sources[(source.type, source.reference)] = source
            return tuple(sources.values())

        return await self.database.transaction(operation)

    async def save_runtime(
        self, scope: Scope, conversation_id: str, environment: ProviderEnvironment
    ) -> None:
        def operation(db: sqlite3.Connection) -> None:
            c = self._conversation(db, conversation_id, scope)
            if c.config.runtime_profile.environment_type != "openai_hosted":
                raise InvalidInput()
            row = db.execute(
                "SELECT environment_id FROM runtime_mappings WHERE conversation_id=?",
                (conversation_id,),
            ).fetchone()
            if row is not None and row[0] != environment.id:
                raise IdempotencyConflict()
            owner = db.execute(
                "SELECT conversation_id FROM runtime_mappings WHERE environment_id=?",
                (environment.id,),
            ).fetchone()
            if owner is not None and owner[0] != conversation_id:
                raise IdempotencyConflict()
            db.execute(
                "INSERT INTO runtime_mappings VALUES(?,?,?) ON CONFLICT(conversation_id) "
                "DO UPDATE SET body=excluded.body",
                (conversation_id, environment.id, environment.model_dump_json()),
            )

        await self.database.transaction(operation)

    async def get_runtime(self, scope: Scope, conversation_id: str) -> ProviderEnvironment | None:
        def operation(db: sqlite3.Connection) -> ProviderEnvironment | None:
            self._conversation(db, conversation_id, scope)
            row = db.execute(
                "SELECT body FROM runtime_mappings WHERE conversation_id=?", (conversation_id,)
            ).fetchone()
            return ProviderEnvironment.model_validate_json(row[0]) if row else None

        return await self.database.transaction(operation)

    async def save_artifacts(
        self, scope: Scope, run_id: str, artifacts: tuple[ArtifactRecord, ...]
    ) -> None:
        def operation(db: sqlite3.Connection) -> None:
            run = self._run(db, run_id)
            c = self._conversation(db, run.conversation_id, scope)
            if len(artifacts) > c.config.runtime_profile.max_artifacts:
                raise InvalidOutput()
            for artifact in artifacts:
                if (
                    artifact.scope != scope
                    or artifact.run_id != run_id
                    or artifact.conversation_id != c.id
                    or artifact.session_id != c.provider_session_id
                    or artifact.turn_id != run.provider_turn_id
                ):
                    raise InvalidOutput()
                row = db.execute(
                    "SELECT body FROM artifacts WHERE session_id=? AND turn_id=? AND provider_id=?",
                    (artifact.session_id, artifact.turn_id, artifact.provider_id),
                ).fetchone()
                if row:
                    old = ArtifactRecord.model_validate_json(row[0])
                    if old.model_dump(exclude={"id"}) != artifact.model_dump(exclude={"id"}):
                        raise InvalidOutput()
                    continue
                db.execute(
                    "INSERT INTO artifacts VALUES(?,?,?,?,?,?,?)",
                    (
                        artifact.id,
                        run_id,
                        c.id,
                        artifact.session_id,
                        artifact.turn_id,
                        artifact.provider_id,
                        artifact.model_dump_json(),
                    ),
                )

            self._save_run(db, run.model_copy(update={"artifacts_finalized": True}))

        await self.database.transaction(operation)

    async def list_artifacts(
        self, scope: Scope, run_id: str, after: str | None = None, limit: int = 50
    ) -> Page[ArtifactRecord]:
        if not 1 <= limit <= 100:
            raise InvalidInput()

        def operation(db: sqlite3.Connection) -> Page[ArtifactRecord]:
            run = self._run(db, run_id)
            self._conversation(db, run.conversation_id, scope)
            if (
                after is not None
                and not db.execute(
                    "SELECT 1 FROM artifacts WHERE id=? AND run_id=?", (after, run_id)
                ).fetchone()
            ):
                raise InvalidCursor()
            if run.state != "completed":
                return Page(items=())
            rows = db.execute(
                "SELECT body FROM artifacts WHERE run_id=? AND id>? ORDER BY id LIMIT ?",
                (run_id, after or "", limit + 1),
            ).fetchall()
            items = tuple(ArtifactRecord.model_validate_json(r[0]) for r in rows[:limit])
            return Page(items=items, next_cursor=items[-1].id if len(rows) > limit else None)

        return await self.database.transaction(operation)

    async def get_artifact(self, scope: Scope, artifact_id: str) -> ArtifactRecord:
        def operation(db: sqlite3.Connection) -> ArtifactRecord:
            row = db.execute("SELECT body FROM artifacts WHERE id=?", (artifact_id,)).fetchone()
            if row is None:
                raise NotFound()
            record = ArtifactRecord.model_validate_json(row[0])
            self._conversation(db, record.conversation_id, scope)
            if self._run(db, record.run_id).state != "completed":
                raise NotFound()
            return record

        return await self.database.transaction(operation)

    async def load_tool_results(self, session_id: str, turn_id: str) -> tuple[ToolResult, ...]:
        return await self.database.transaction(
            lambda db: tuple(
                ToolResult.model_validate_json(r[0])
                for r in db.execute(
                    "SELECT result FROM tool_calls WHERE session_id=? AND turn_id=? "
                    "AND result IS NOT NULL",
                    (session_id, turn_id),
                ).fetchall()
            )
        )

    async def get_saved_artifacts(
        self, scope: Scope, run_id: str
    ) -> tuple[ArtifactRecord, ...] | None:
        """Internal recovery loader; public listing still requires completed root state."""

        def operation(db: sqlite3.Connection) -> tuple[ArtifactRecord, ...] | None:
            run = self._run(db, run_id)
            self._conversation(db, run.conversation_id, scope)
            if not run.artifacts_finalized:
                return None
            return tuple(
                ArtifactRecord.model_validate_json(r[0])
                for r in db.execute(
                    "SELECT body FROM artifacts WHERE run_id=? ORDER BY id", (run_id,)
                ).fetchall()
            )

        return await self.database.transaction(operation)
