"""Operator preflight; never prints credentials or upstream/database exceptions."""

import argparse
import asyncio
import json

from app.auth import Principal
from app.database import Database
from app.query import compile_query
from app.settings import Catalog, ConfigurationError, Settings


async def check(settings: Settings) -> None:
    db = Database(settings)
    async with await db.connect() as conn:
        await conn.execute("SELECT 1 FROM mcp_control.results LIMIT 0")
        await conn.execute("SELECT 1 FROM mcp_control.refreshes LIMIT 0")
        await conn.execute("SELECT 1 FROM mcp_control.revoked_tokens LIMIT 0")
    for shop, config in settings.shops.items():
        who = Principal(subject="operator-preflight", shop=shop, scopes={"data:read"})
        for dataset in settings.datasets:
            if dataset.id in config.datasets and dataset.layer == "mart":
                await db.query(who, compile_query(f"SELECT * FROM {dataset.id} LIMIT 0", [dataset]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--connect", action="store_true", help="Check control and mart connectivity")
    mode.add_argument(
        "--schema",
        choices=["config", "catalog"],
        help="Print an editor JSON Schema; no credentials or connection required",
    )
    args = parser.parse_args()
    if args.schema:
        model = Settings if args.schema == "config" else Catalog
        print(json.dumps(model.model_json_schema(), indent=2))
        return
    try:
        settings = Settings.load()
        if args.connect:
            asyncio.run(check(settings))
    except ConfigurationError as exc:
        raise SystemExit(f"Preflight failed: {exc}") from None
    except Exception:
        raise SystemExit("Preflight failed; check roles, CA and schema") from None
    print("Preflight passed; live identity/upstream/isolation verification is still required")


if __name__ == "__main__":
    main()
