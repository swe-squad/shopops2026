import argparse
import asyncio
import importlib
from datetime import UTC, datetime, timedelta

from app.config.settings import Settings
from app.contracts.identity import Scope
from scripts._admin import maintenance


async def cleanup(args: argparse.Namespace) -> None:
    settings = Settings.from_env()
    async with maintenance(settings) as repository:
        if args.action == "prune":
            cutoff = (
                args.before
                or (datetime.now(UTC) - timedelta(days=settings.history_retention_days)).isoformat()
            )
            messages, events = await repository.prune(cutoff)
            print(f"Pruned messages={messages}, events={events}; active runs preserved.")
            return
        provider = None
        if args.provider_factory:
            module, name = args.provider_factory.split(":", 1)
            provider = getattr(importlib.import_module(module), name)(settings)

        async def delete_session(session_id: str) -> None:
            if provider is None:
                raise RuntimeError("Provider factory required for session cleanup")
            await provider.delete_session(session_id)

        await repository.delete_conversation(
            Scope(tenant_id=args.tenant, shop_id=args.shop, user_id=args.user),
            args.conversation,
            delete_session,
        )
    print("Conversation and provider session deleted.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Trusted operator cleanup; stop app first")
    commands = parser.add_subparsers(dest="action", required=True)
    delete = commands.add_parser("delete")
    for name in ("tenant", "shop", "user", "conversation"):
        delete.add_argument(f"--{name}", required=True)
    delete.add_argument(
        "--provider-factory", help="Trusted module:function returning AgentProvider"
    )
    prune = commands.add_parser("prune")
    prune.add_argument("--before", help="ISO-8601 UTC cutoff, defaults to HISTORY_RETENTION_DAYS")
    try:
        asyncio.run(cleanup(parser.parse_args()))
    except Exception:
        raise SystemExit(
            "Maintenance failed; inspect configuration/provider status before retry"
        ) from None


if __name__ == "__main__":
    main()
