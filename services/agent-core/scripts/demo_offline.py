import argparse
import json
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse
from uuid import uuid4


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Synthetic offline API demo; requires T02–T04 wiring"
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--fixture-token", required=True)
    parser.add_argument("--shop", default="shop-a")
    args = parser.parse_args()
    parsed = urlparse(args.base_url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        parser.error("Offline demo requires a loopback HTTP base URL")

    def request(path: str, body: dict | None = None) -> dict:
        payload = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(
            args.base_url + path,
            data=payload,
            headers={
                "Authorization": f"Bearer {args.fixture_token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            raise SystemExit(
                f"Demo HTTP {error.code}; verify T02–T04 integration and fixture token"
            ) from None

    orchestrator = request(
        f"/api/v1/shops/{args.shop}/orchestrator",
        {"template_id": "shopops", "config_revision": "returns-v1"},
    )
    conversation = request(
        f"/api/v1/shops/{args.shop}/conversations",
        {
            "orchestrator_id": orchestrator["orchestrator_id"],
            "client_conversation_id": str(uuid4()),
        },
    )
    cid = conversation["conversation_id"]
    for text in (
        "Tỷ lệ hoàn SKU-A từ 2026-10-01 đến 2026-10-07 thay đổi thế nào?",
        "Chính sách xử lý khi khách phàn nàn về kích thước là gì?",
    ):
        message = request(
            f"/api/v1/conversations/{cid}/messages",
            {"client_message_id": str(uuid4()), "content": text},
        )
        until = time.monotonic() + 250
        while time.monotonic() < until:
            run = request(f"/api/v1/runs/{message['run_id']}")
            if run["status"] in {"completed", "failed", "cancelled"}:
                print(
                    json.dumps(
                        {"status": run["status"], "response": run.get("response")},
                        ensure_ascii=False,
                    )
                )
                if run["status"] != "completed":
                    raise SystemExit("Synthetic demo run did not complete")
                break
            time.sleep(0.2)
        else:
            raise SystemExit("Synthetic demo polling deadline exceeded")
    history = request(f"/api/v1/conversations/{cid}/history")
    print(f"Synthetic demo complete; history items={len(history['items'])}")


if __name__ == "__main__":
    main()
