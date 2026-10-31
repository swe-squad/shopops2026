"""Explicit live preflight. Never report AC13 success while foundation v1 is blocked."""

import argparse


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True)
    parser.parse_args()
    print("AC13 UNVERIFIED: foundation v1 needs atomic session creation with initial input.")
    print("T01 must amend the contract and pin openai==3.42.0; then wire T04 and scoped cleanup.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
