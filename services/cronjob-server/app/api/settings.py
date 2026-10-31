from fastapi import FastAPI, Request
from psycopg.types.json import Jsonb
from pydantic import ValidationError

from app.api.common import APIError
from app.api.contracts import MartSettings, SettingsPatch
from app.pipeline.publish import digest
from app.storage.db import connect


def register(app: FastAPI) -> None:
    @app.get("/v1/admin/mart-settings", response_model=MartSettings)
    def get_settings() -> dict:
        with connect() as conn:
            return conn.execute(
                "SELECT as_of,recent_days,baseline_days FROM mart.settings"
            ).fetchone()

    @app.patch("/v1/admin/mart-settings", response_model=MartSettings)
    def patch_settings(request: Request, body: SettingsPatch) -> dict:
        key = request.headers.get("Idempotency-Key", "")
        if not key or len(key) > 200:
            raise APIError(422, "INVALID_IDEMPOTENCY_KEY")
        if request.query_params:
            raise APIError(422, "INVALID_FILTER")
        intent = body.model_dump(mode="json", exclude_unset=True)
        with connect() as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,8173604))", ("admin" + key,)
            )
            if conn.execute(
                "SELECT 1 FROM sync.runs WHERE actor='admin' AND idempotency_key=%s", (key,)
            ).fetchone():
                raise APIError(409, "IDEMPOTENCY_CONFLICT")
            current = conn.execute(
                "SELECT as_of,recent_days,baseline_days FROM mart.settings FOR UPDATE"
            ).fetchone()
            old = conn.execute(
                "SELECT * FROM sync.settings_receipts WHERE idempotency_key=%s", (key,)
            ).fetchone()
            if old:
                if old["intent_hash"] != digest(intent):
                    raise APIError(409, "IDEMPOTENCY_CONFLICT")
                return old["response"]
            try:
                updated = MartSettings.model_validate(current | intent)
            except ValidationError:
                raise APIError(422, "VALIDATION_ERROR") from None
            conn.execute(
                "UPDATE mart.settings SET as_of=%s,recent_days=%s,baseline_days=%s",
                (updated.as_of, updated.recent_days, updated.baseline_days),
            )
            result = updated.model_dump(mode="json")
            conn.execute(
                "INSERT INTO sync.settings_receipts VALUES (%s,%s,%s)",
                (key, digest(intent), Jsonb(result)),
            )
            return result
