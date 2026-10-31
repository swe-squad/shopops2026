"""Database I/O with separate control and restricted query identities."""

import json
from datetime import UTC, datetime
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.auth import Principal
from app.settings import Settings


class Database:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def connect(self):
        return await psycopg.AsyncConnection.connect(
            self.settings.control_dsn.get_secret_value(), connect_timeout=5, row_factory=dict_row
        )

    async def query(self, who: Principal, sql: str) -> dict:
        dsn = self.settings.shops[who.shop].query_dsn.get_secret_value()
        async with await psycopg.AsyncConnection.connect(dsn, connect_timeout=5) as conn:
            # Scope comes from the database login, not a model-settable session variable.
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT rolsuper, rolbypassrls, rolcreaterole, rolcreatedb, rolreplication "
                    "FROM pg_roles WHERE rolname=current_user"
                )
                privileged = await cursor.fetchone()
                if not privileged or any(privileged):
                    raise ValueError("Query identity must not be privileged")
                await conn.commit()
                await cursor.execute("BEGIN READ ONLY")
                await cursor.execute(
                    "SELECT set_config('statement_timeout', %s, true)",
                    (str(self.settings.query_timeout_ms),),
                )
                await cursor.execute("SET LOCAL search_path = pg_catalog")
                # Server-side cursor prevents a huge result buffering in the application.
                async with conn.cursor(name="bounded_result") as stream:
                    await stream.execute(sql)
                    rows = await stream.fetchmany(self.settings.max_rows + 1)
                    columns = [c.name for c in stream.description]
                    if len(columns) != len(set(columns)):
                        raise ValueError("Give result columns unique aliases")
                    truncated = len(rows) > self.settings.max_rows
                    payload = {
                        "columns": columns,
                        "rows": [
                            dict(zip(columns, row, strict=False))
                            for row in rows[: self.settings.max_rows]
                        ],
                        "truncated": truncated,
                    }
                    # Decimal/date values stay exact strings rather than lossy floats.
                    payload = json.loads(json.dumps(payload, default=str))
                    if len(json.dumps(payload).encode()) > self.settings.max_bytes:
                        raise ValueError("Result too large; aggregate or narrow the query")
                    return payload

    async def save(
        self, who: Principal, payload: dict, grants: list[str], expires: datetime
    ) -> str:
        key = uuid4().hex
        size = len(json.dumps(payload).encode())
        async with await self.connect() as conn:
            # Serialize the per-shop quota check with all writers for that shop.
            await conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (who.shop,))
            await conn.execute(
                "DELETE FROM mcp_control.results WHERE shop_key=%s AND expires_at <= now()",
                (who.shop,),
            )
            cursor = await conn.execute(
                "SELECT coalesce(sum(bytes),0) AS size FROM mcp_control.results WHERE shop_key=%s",
                (who.shop,),
            )
            if (await cursor.fetchone())["size"] + size > self.settings.workspace_bytes:
                raise ValueError("Workspace quota exceeded")
            await conn.execute(
                "INSERT INTO mcp_control.results VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (key, who.shop, who.subject, Jsonb(payload), grants, expires, size),
            )
        return key

    async def read(self, who: Principal, key: str) -> dict:
        async with await self.connect() as conn:
            cursor = await conn.execute(
                "SELECT payload, grants, expires_at FROM mcp_control.results "
                "WHERE id=%s AND shop_key=%s AND subject=%s AND expires_at>now()",
                (key, who.shop, who.subject),
            )
            row = await cursor.fetchone()
        if not row:
            raise ValueError("Result unavailable or expired")
        return row

    async def drop(self, who: Principal, key: str) -> None:
        async with await self.connect() as conn:
            await conn.execute(
                "DELETE FROM mcp_control.results WHERE id=%s AND shop_key=%s AND subject=%s",
                (key, who.shop, who.subject),
            )

    async def reserve_refresh(self, who: Principal, key: str, body: dict) -> dict:
        async with await self.connect() as conn:
            await conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (who.shop,))
            cursor = await conn.execute(
                "SELECT body, operation_id FROM mcp_control.refreshes "
                "WHERE shop_key=%s AND subject=%s AND idempotency_key=%s",
                (who.shop, who.subject, key),
            )
            old = await cursor.fetchone()
            if old:
                if old["body"] != body:
                    raise ValueError("Idempotency key belongs to another request")
                return old
            cursor = await conn.execute(
                "SELECT 1 FROM mcp_control.refreshes WHERE shop_key=%s AND created_at > %s",
                (
                    who.shop,
                    datetime.fromtimestamp(
                        datetime.now(UTC).timestamp() - self.settings.refresh_cooldown_seconds, UTC
                    ),
                ),
            )
            if await cursor.fetchone():
                raise ValueError("Refresh cooldown active")
            await conn.execute(
                "INSERT INTO mcp_control.refreshes(shop_key,subject,idempotency_key,body) "
                "VALUES (%s,%s,%s,%s)",
                (who.shop, who.subject, key, Jsonb(body)),
            )
        return {"body": body, "operation_id": None}

    async def attach_operation(self, who: Principal, key: str, operation_id: str) -> None:
        async with await self.connect() as conn:
            await conn.execute(
                "UPDATE mcp_control.refreshes SET operation_id=%s "
                "WHERE shop_key=%s AND subject=%s AND idempotency_key=%s",
                (operation_id, who.shop, who.subject, key),
            )

    async def operation_owned(self, who: Principal, operation_id: str) -> bool:
        async with await self.connect() as conn:
            cursor = await conn.execute(
                "SELECT 1 FROM mcp_control.refreshes "
                "WHERE shop_key=%s AND subject=%s AND operation_id=%s",
                (who.shop, who.subject, operation_id),
            )
            return bool(await cursor.fetchone())
