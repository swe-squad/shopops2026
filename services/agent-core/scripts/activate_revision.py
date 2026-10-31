import argparse
import asyncio

from app.config.settings import Settings
from app.contracts.identity import Scope
from scripts._admin import maintenance


async def activate(args: argparse.Namespace) -> None:
    async with maintenance(Settings.from_env()) as repository:
        await repository.activate_revision(
            Scope(tenant_id=args.tenant, shop_id=args.shop, user_id=args.user),
            args.template,
            args.revision,
        )
    print("Revision activated; existing conversation snapshots preserved.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Activate a registered immutable revision offline")
    for name in ("tenant", "shop", "user", "template", "revision"):
        parser.add_argument(f"--{name}", required=True)
    try:
        asyncio.run(activate(parser.parse_args()))
    except Exception:
        raise SystemExit(
            "Maintenance failed; inspect configuration/provider status before retry"
        ) from None


if __name__ == "__main__":
    main()
