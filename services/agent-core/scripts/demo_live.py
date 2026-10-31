"""Opt-in synthetic live Agents API/MCP smoke with session cleanup."""

import argparse
import json
from pathlib import Path

from scripts.live_smoke import run_live_smoke


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True)
    parser.add_argument("--model")
    parser.add_argument("--credentials-file")
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    result = run_live_smoke(
        model=args.model,
        credentials_file=args.credentials_file,
    )
    encoded = json.dumps(result, ensure_ascii=False)
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(encoded + "\n")
    print(encoded)
    return 0 if result["status"] == "passed" and result["cleanup"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
