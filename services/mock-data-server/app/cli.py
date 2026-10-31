import argparse

from app.storage.migrations import migrate
from app.storage.seed import seed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["migrate", "seed"])
    parser.add_argument("--profile", choices=["mvp"], default="mvp")
    args = parser.parse_args()
    if args.command == "migrate":
        migrate()
        print("Migrations applied")
    else:
        print(seed())


if __name__ == "__main__":
    main()
