import argparse

from app.storage.migrations import migrate
from app.storage.product_images import backfill
from app.storage.seed import seed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["migrate", "seed", "backfill-product-images"])
    parser.add_argument("--apply", action="store_true", help="Apply the product image backfill")
    parser.add_argument("--profile", choices=["mvp"], default="mvp")
    args = parser.parse_args()
    if args.command == "migrate":
        migrate()
        print("Migrations applied")
    elif args.command == "backfill-product-images":
        print(backfill(apply=args.apply))
    else:
        print(seed())


if __name__ == "__main__":
    main()
