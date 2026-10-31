"""Explicit hosted acceptance entry point; both acknowledgements are mandatory."""

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True)
    parser.add_argument("--hosted", action="store_true", required=True)
    parser.add_argument("--credentials-file")
    parser.add_argument("--evidence", type=Path, default=Path(".evidence/live-hosted.json"))
    args = parser.parse_args()
    # Argument validation must precede imports that can load credentials or providers.
    from scripts.hosted_smoke import run_hosted_smoke

    result = run_hosted_smoke(
        live=args.live,
        hosted=args.hosted,
        credentials_file=args.credentials_file,
    )
    encoded = json.dumps(result, ensure_ascii=False)
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(encoded + "\n")
    print(encoded)
    return (
        0 if result["status"] == "passed" and result["cleanup"] and result["local_cleanup"] else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
