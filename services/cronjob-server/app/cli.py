import argparse

from app.storage.migrations import migrate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["migrate"])
    parser.parse_args()
    migrate()
    print("Migrations applied")


if __name__ == "__main__":
    main()
