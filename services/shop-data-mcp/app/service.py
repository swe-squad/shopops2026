"""Authorized analytical workflows independent of MCP transport."""

import asyncio
import json
import re
from datetime import UTC, datetime, timedelta

from sqlglot import exp, parse_one

from app.auth import Principal
from app.cronjob import CronjobUpstream
from app.database import Database
from app.query import compile_query
from app.settings import Settings
from app.upstream import Upstream


class DataService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.db = Database(settings)
        self.query_slots = asyncio.Semaphore(2)

        def secret(value):
            return value.get_secret_value() if value else None

        self.approval = Upstream(settings.approval_url, secret(settings.approval_token))
        self.ingestion = Upstream(settings.ingestion_url, secret(settings.ingestion_token))
        self.cronjob = CronjobUpstream(settings.ingestion_url, secret(settings.ingestion_token))

    def catalog(self, who: Principal) -> list:
        permitted = self.settings.shops[who.shop].datasets
        return [d for d in self.settings.datasets if d.id in permitted]

    @staticmethod
    def require(who: Principal, scope: str) -> None:
        if scope not in who.scopes:
            raise ValueError("Permission denied")

    async def grant(self, who: Principal, key: str) -> dict:
        self.require(who, "raw:read")
        grant = await self.approval.request(
            "GET", f"/v1/grants/{key}", params={"subject": who.subject, "shop_key": who.shop}
        )
        if (
            grant.get("subject") != who.subject
            or grant.get("shop_key") != who.shop
            or grant.get("status") != "approved"
        ):
            raise ValueError("Raw grant unavailable")
        expiry = datetime.fromisoformat(grant["expires_at"])
        if expiry <= datetime.now(UTC) or grant.get("grant_id") != key:
            raise ValueError("Raw grant expired or invalid")
        self.window(grant["start"], grant["end"])
        return grant

    @staticmethod
    def window(start: str, end: str) -> tuple[datetime, datetime]:
        a, b = datetime.fromisoformat(start), datetime.fromisoformat(end)
        if a.tzinfo is None or b.tzinfo is None or a >= b:
            raise ValueError("Use a nonempty timezone-aware [start,end) window")
        return a.astimezone(UTC), b.astimezone(UTC)

    async def analyze(
        self, who: Principal, query: str, grant_id: str | None = None, source_id: str | None = None
    ) -> dict:
        self.require(who, "data:read")
        grant = await self.grant(who, grant_id) if grant_id else None
        dependencies = [grant_id] if grant_id else []
        snapshots = {grant_id: json.dumps(grant, sort_keys=True)} if grant else {}
        expires = datetime.now(UTC) + timedelta(seconds=self.settings.ttl_seconds)
        temporary = {}
        input_truncated = False
        if source_id:
            saved = await self.read(who, source_id)
            temporary["temp"] = saved["payload"]
            input_truncated = bool(
                saved["payload"].get("truncated") or saved["payload"].get("input_truncated")
            )
            dependencies += saved["grants"]
            snapshots.update(saved["payload"].get("grant_snapshots", {}))
            expires = min(expires, saved["expires_at"])
        if grant:
            expires = min(expires, datetime.fromisoformat(grant["expires_at"]))
        datasets = self.catalog(who)
        if not grant:
            datasets = [d for d in datasets if d.layer == "mart"]
        sql = compile_query(query, datasets, grant, temporary)
        async with self.query_slots:
            result = await self.db.query(who, sql)
        # Revocation/expiry during a query must prevent result release.
        for key in set(dependencies):
            current = await self.grant(who, key)
            if snapshots.get(key) != json.dumps(current, sort_keys=True):
                raise ValueError("Source grant changed")
        if expires <= datetime.now(UTC):
            raise ValueError("Source expired during query")
        used = {t.name for t in parse_one(query, read="postgres").find_all(exp.Table)}
        result["provenance"] = {
            "catalog": [d.model_dump() for d in datasets if d.id in used],
            "queried_at": datetime.now(UTC).isoformat(),
        }
        result["input_truncated"] = input_truncated
        result["grant_snapshots"] = snapshots
        result_id = await self.db.save(who, result, list(set(dependencies)), expires)
        return {
            "shop_key": who.shop,
            "result_id": result_id,
            "columns": result["columns"],
            "preview": result["rows"][:20],
            "truncated": result["truncated"],
            "input_truncated": input_truncated,
            "expires_at": expires.isoformat(),
            "provenance": result["provenance"],
        }

    async def read(self, who: Principal, key: str) -> dict:
        saved = await self.db.read(who, key)
        for grant in saved["grants"]:
            current = await self.grant(who, grant)
            expected = saved["payload"].get("grant_snapshots", {}).get(grant)
            if expected != json.dumps(current, sort_keys=True):
                raise ValueError("Source grant changed")
        return saved

    async def refresh(self, who: Principal, resource: str, start: str, end: str, key: str) -> dict:
        self.require(who, "data:refresh")
        a, b = self.window(start, end)
        now = datetime.now(UTC)
        if a < now - timedelta(days=self.settings.refresh_lookback_days) or b > now:
            raise ValueError("Refresh outside permitted lookback")
        if resource not in {
            d.resource for d in self.catalog(who) if d.resource
        } or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", key):
            raise ValueError("Unsupported refresh resource or key")
        body = {
            "subject": who.subject,
            "shop_key": who.shop,
            "resource": resource,
            "start": a.isoformat(),
            "end": b.isoformat(),
            "idempotency_key": key,
        }
        saved = await self.db.reserve_refresh(who, key, body)
        if saved["operation_id"]:
            return {"operation_id": saved["operation_id"], "status": "submitted"}
        result = await self.ingestion.request("POST", "/v1/refreshes", body=body)
        operation = result.get("operation_id", "")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", operation) or result.get("status") not in {
            "queued",
            "collecting",
            "raw_available",
            "processing",
            "mart_ready",
            "snapshot_ready",
            "failed",
            "cancelled",
            "partial",
        }:
            raise ValueError("Invalid upstream operation")
        await self.db.attach_operation(who, key, operation)
        return {"operation_id": operation, "status": result.get("status")}
