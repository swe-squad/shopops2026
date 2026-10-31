"""Offline T10 acceptance. Run with Core Python; requires Docker and service venvs.

Owns disposable PostgreSQL and loopback HTTP processes. No operational databases,
.env files, sibling Python imports or model calls. Source fixture JSON is the
independent oracle; only child processes import each service's own runtime.
"""

import argparse
import hashlib
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4
from zoneinfo import ZoneInfo

CORE = Path(__file__).resolve().parents[1]
ROOT = CORE.parents[1]
SERVICES = ROOT / "services"
SHOP = "shopee-open-platform:1001"
PHONE = "+84900000001"


def command(args, **kwargs):
    result = subprocess.run(args, capture_output=True, text=True, **kwargs)
    if result.returncode:
        raise RuntimeError(f"Setup failed: {args[0:3]}: {result.stderr[-1200:]}")
    return result.stdout.strip()


def port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def request(url, body=None, headers=None, method=None, raw=False):
    req = Request(
        url,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", **(headers or {})},
        method=method,
    )
    with urlopen(req, timeout=60) as response:
        content = response.read()
    return content if raw else json.loads(content)


def wait(url):
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        try:
            request(url)
            return
        except URLError, TimeoutError, ConnectionError:
            time.sleep(0.2)
    raise RuntimeError("HTTP readiness deadline exceeded")


def denied(url, headers, body=None, status=404):
    try:
        request(url, body, headers)
    except HTTPError as error:
        assert error.code == status
    else:
        raise AssertionError("Scope rejection missing")


def mcp_call(url, phone, tool, arguments):
    headers = {"X-Phone-Number": phone, "Accept": "application/json, text/event-stream"}
    request(
        url,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "t10-acceptance", "version": "1"},
            },
        },
        headers,
        raw=True,
    )
    raw = request(
        url,
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments},
        },
        headers,
        raw=True,
    ).decode()
    response = (
        json.loads(next(line[6:] for line in raw.splitlines() if line.startswith("data: ")))
        if raw.startswith("event:")
        else json.loads(raw)
    )
    return response["result"]


def oracle(fixture):
    """Compute from source records, without SQL, projections or adapter code."""
    local = ZoneInfo("Asia/Ho_Chi_Minh")
    cutoff = datetime.fromisoformat("2026-10-31T00:00:00+07:00")

    def date_of(value):
        return datetime.fromisoformat(value).astimezone(local).date().isoformat()

    sku_orders = {i["order_id"] for i in fixture["order_items"] if i["sku"] == "SHIRT-M"}
    returned = {
        r["order_id"]
        for r in fixture["returns"]
        if datetime.fromisoformat(r["requested_at"]) < cutoff
    }

    def count(start, end):
        ids = {
            o["order_id"]
            for o in fixture["orders"]
            if o["order_id"] in sku_orders
            and o["status"] in {"shipped", "completed"}
            and start <= date_of(o["ordered_at"]) <= end
            and datetime.fromisoformat(o["updated_at"]) <= cutoff
        }
        returns = len(ids & returned)
        return {
            "orders": len(ids),
            "returns": returns,
            "return_rate": round(100 * returns / len(ids), 6) if ids else None,
        }

    recent, baseline = count("2026-10-24", "2026-10-30"), count("2026-10-17", "2026-10-23")
    reviews = [
        r
        for r in fixture["reviews"]
        if r["sku"] == "SHIRT-M" and "2026-10-24" <= date_of(r["reviewed_at"]) <= "2026-10-30"
    ]
    categories = {
        "negative_rating": sum(r["rating"] <= 2 for r in reviews),
        "sizing_mentions": sum(
            r["rating"] <= 2 and bool(re.search("chật|nhỏ|size", r["body"], re.I)) for r in reviews
        ),
    }
    return recent, baseline, categories


# Runs in the MCP service's own process/interpreter, never imports sibling code.
MCP_SETUP = r"""
import json, os
from pathlib import Path
import psycopg
from psycopg import sql
from app.provision import provision
config=json.loads(Path(os.environ['T10_MCP_CONFIG']).read_text())
with psycopg.connect(os.environ['T10_SOURCE_DSN']) as c:
    c.execute(Path('migrations/005-source-membership.sql').read_text())
    c.execute(Path('migrations/003-phone-membership.sql').read_text())
    c.execute(sql.SQL('ALTER ROLE mcp_membership PASSWORD {}').format(
        sql.Literal(os.environ['T10_PASSWORD'])))
with psycopg.connect(os.environ['T10_DERIVED_DSN']) as c:
    c.execute(Path('migrations/002-pipeline-access.sql').read_text())
    c.execute(Path('migrations/004-agent-projections.sql').read_text())
    for index,shop in enumerate(config['shops']):
        role='t10_shop_'+str(index)
        provision(c,shop,role)
        c.execute(sql.SQL('ALTER ROLE {} PASSWORD {}').format(
            sql.Identifier(role),sql.Literal(os.environ['T10_PASSWORD'])))
with psycopg.connect(config['control_dsn']) as c:
    c.execute(Path('migrations/001-control.sql').read_text())
"""

# Test-only TLS relaxation for a disposable loopback DB; production loader unchanged.
MCP_SERVE = r"""
import json, os
from pathlib import Path
from app.settings import Settings
def test_settings(cls):
    return cls.model_validate(json.loads(Path(os.environ['T10_MCP_CONFIG']).read_text()))
Settings.load=classmethod(test_settings)
from app.main import create_app
import uvicorn
uvicorn.run(create_app(),host='127.0.0.1',port=int(os.environ['PORT']),access_log=False)
"""


def verify_complete_projection(fixture, rows):
    """All fixture SKUs/facts, independent of production SQL and adapter aggregation."""
    cutoff = datetime.fromisoformat(rows["snapshot"][0]["analysis_as_of"])
    local = ZoneInfo("Asia/Ho_Chi_Minh")
    assert rows["snapshot"][0]["source_revision"] == rows["source_revision"] == 1
    assert rows["source_counts"] == {table: len(records) for table, records in fixture.items()}
    assert cutoff >= datetime.fromisoformat("2026-10-31T00:00:00+07:00")
    expected_skus = sorted(p["sku"] for p in fixture["products"])
    assert sorted(r["sku"] for r in rows["skus"]) == expected_skus
    returned = {
        r["order_id"]
        for r in fixture["returns"]
        if datetime.fromisoformat(r["requested_at"]) < cutoff
    }
    orders = {
        o["order_id"]: o
        for o in fixture["orders"]
        if o["status"] in {"shipped", "completed"}
        and datetime.fromisoformat(o["ordered_at"]) < cutoff
        and datetime.fromisoformat(o["updated_at"]) <= cutoff
    }
    expected = {
        (
            i["sku"],
            i["order_id"],
            datetime.fromisoformat(orders[i["order_id"]]["ordered_at"])
            .astimezone(local)
            .date()
            .isoformat(),
            i["order_id"] in returned,
        )
        for i in fixture["order_items"]
        if i["order_id"] in orders
    }
    actual = {
        (r["sku"], r["order_id"], r["business_date"], r["has_return"]) for r in rows["orders"]
    }
    assert actual == expected and len(rows["orders"]) == len(expected)
    expected_reviews = {
        (
            r["sku"],
            r["review_id"],
            datetime.fromisoformat(r["reviewed_at"]).astimezone(local).date().isoformat(),
            r["rating"] <= 2,
            r["rating"] <= 2 and bool(re.search("chật|nhỏ|size", r["body"], re.I)),
        )
        for r in fixture["reviews"]
        if datetime.fromisoformat(r["reviewed_at"]) < cutoff
    }
    actual_reviews = {
        (r["sku"], r["review_id"], r["business_date"], r["negative_rating"], r["sizing_mentions"])
        for r in rows["reviews"]
    }
    assert expected_reviews == actual_reviews and len(rows["reviews"]) == len(expected_reviews)
    assert all(r["source_document_id"] for r in rows["reviews"])
    return {
        "coverage_start": "2026-10-17",
        "all_skus": len(expected_skus),
        "cohorts": len(expected),
        "reviews": len(expected_reviews),
        "fixture_sha256": hashlib.sha256(json.dumps(fixture, sort_keys=True).encode()).hexdigest(),
    }


PROJECTION_READ = r"""
import json, os
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
config=json.loads(Path(os.environ['T10_MCP_CONFIG']).read_text())
rows={}
with psycopg.connect(config['shops']['shopee-open-platform:1001']['query_dsn'],
                     row_factory=dict_row) as c:
    for name,table in [('snapshot','agent_snapshot_v1'), ('skus','agent_sku_catalog_v1'),
                       ('orders','agent_order_cohorts_v1'), ('reviews','agent_review_facts_v1')]:
        rows[name]=c.execute('SELECT * FROM mcp_data.'+table).fetchall()
with psycopg.connect(os.environ['T10_SOURCE_DSN']) as c:
    rows['source_revision']=c.execute('SELECT revision FROM mock.state').fetchone()[0]
    rows['source_counts']={}
    for table in ('shops','products','promotions','orders','order_items','reviews','returns',
                  'inventory','settlements','fulfillment','account_health'):
        rows['source_counts'][table]=c.execute(
            'SELECT count(*) FROM mock.'+table+' WHERE shop_key=%s',
            ('shopee-open-platform:1001',)).fetchone()[0]
print(json.dumps(rows,default=str))
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pipeline-python", type=Path, required=True)
    parser.add_argument("--chat-python", type=Path)
    args = parser.parse_args()
    pipeline = str(args.pipeline_python.absolute())
    mcp_python = str(SERVICES / "shop-data-mcp/.venv/bin/python")
    chat_python = str(args.chat_python.absolute()) if args.chat_python else pipeline
    name = "t10-acceptance-" + uuid4().hex[:12]
    processes = []
    created = False
    # Deliberately do not inherit service config/secrets from the operator shell.
    env = {key: os.environ[key] for key in ("PATH", "HOME", "LANG") if key in os.environ}
    process_env = env.copy()
    env.update(
        POSTGRES_HOST="127.0.0.1",
        POSTGRES_USER="postgres",
        POSTGRES_PASSWORD=secrets.token_urlsafe(24),
        POSTGRES_DB="source_test",
        POSTGRES_SSLMODE="disable",
        SYNC_INTERVAL_SECONDS="0",
        MCP_SERVICE_TOKEN=secrets.token_urlsafe(32),
        MCP_SUBJECT_USERS_JSON=json.dumps({PHONE: PHONE}),
    )
    evidence = {"hosted_execution": False, "passed": False}
    try:
        command(
            [
                "docker",
                "run",
                "--detach",
                "--rm",
                "--name",
                name,
                "--publish",
                "127.0.0.1::5432",
                "--env",
                "POSTGRES_PASSWORD",
                "--env",
                "POSTGRES_DB",
                "postgres:17-alpine",
            ],
            env=env,
        )
        created = True
        binding = command(["docker", "port", name, "5432/tcp"])
        assert binding.startswith("127.0.0.1:")
        env["POSTGRES_PORT"] = binding.rsplit(":", 1)[1]
        deadline = time.monotonic() + 40
        while subprocess.run(
            ["docker", "exec", name, "pg_isready", "-h", "127.0.0.1", "-U", "postgres"],
            capture_output=True,
        ).returncode:
            if time.monotonic() > deadline:
                raise RuntimeError("PostgreSQL readiness deadline exceeded")
            time.sleep(0.2)
        for db in ("derived_test", "control_test"):
            command(["docker", "exec", name, "createdb", "-U", "postgres", db])
        with tempfile.TemporaryDirectory(prefix="t10-acceptance-") as temporary:
            temp = Path(temporary)
            with (temp / "services.log").open("w+") as log:

                def launch(directory, python, arguments, service_env, url, health):
                    process = subprocess.Popen(
                        [python, *arguments], cwd=directory, env=service_env, stdout=log, stderr=log
                    )
                    processes.append(process)
                    try:
                        if process.poll() is not None:
                            raise RuntimeError("Service exited during startup")
                        wait(url + health)
                    except Exception:
                        log.flush()
                        log.seek(0)
                        # Local fixture logs only; do not print config/DSNs.
                        diagnostic = log.read()[-2500:]
                        diagnostic = diagnostic.replace(env["POSTGRES_PASSWORD"], "[redacted]")
                        raise RuntimeError("Service startup failed: " + diagnostic) from None
                    return process

                def serve(directory, python, module, service_env, url, health):
                    return launch(
                        directory,
                        python,
                        [
                            "-m",
                            "uvicorn",
                            module,
                            "--host",
                            "127.0.0.1",
                            "--port",
                            url.rsplit(":", 1)[1],
                            "--no-access-log",
                        ],
                        service_env,
                        url,
                        health,
                    )

                urls = {
                    s: f"http://127.0.0.1:{port()}"
                    for s in ("source", "cron", "mcp", "core", "chat")
                }
                env["MOCK_DATA_SERVER_URL"] = urls["source"]
                for service, database, key in (
                    ("mock-data-server", "source_test", "source"),
                    ("cronjob-server", "derived_test", "cron"),
                ):
                    directory = SERVICES / service
                    service_env = env | {"POSTGRES_DB": database}
                    command([pipeline, "-m", "app.cli", "migrate"], cwd=directory, env=service_env)
                    if key == "source":
                        command([pipeline, "-m", "app.cli", "seed"], cwd=directory, env=service_env)
                    serve(
                        directory, pipeline, "app.main:app", service_env, urls[key], "/health/ready"
                    )

                def sync():
                    headers = {"X-Demo-User-Id": PHONE, "Idempotency-Key": uuid4().hex}
                    run = request(urls["cron"] + "/v1/sync-runs", {}, headers)
                    deadline = time.monotonic() + 40
                    while True:
                        state = request(urls["cron"] + run["status_url"], headers=headers)
                        if state["status"] == "succeeded":
                            return state
                        assert state["status"] != "failed", "Synchronization failed"
                        assert time.monotonic() < deadline, "Synchronization deadline exceeded"
                        time.sleep(0.2)

                sync()

                def dsn(db, user="postgres"):
                    return (
                        f"host=127.0.0.1 port={env['POSTGRES_PORT']} dbname={db} "
                        f"user={user} password={env['POSTGRES_PASSWORD']} sslmode=disable"
                    )

                catalog = json.loads(
                    (SERVICES / "shop-data-mcp/catalog.agent.example.json").read_text()
                )
                mcp_config = {
                    "control_dsn": dsn("control_test"),
                    "membership_dsn": dsn("source_test", "mcp_membership"),
                    "public_url": "https://mcp.test/mcp",
                    "internal_url": urls["mcp"] + "/mcp",
                    "datasets": catalog["datasets"],
                    "shops": {
                        shop: {
                            "query_dsn": dsn("derived_test", "t10_shop_" + str(index)),
                            "datasets": [d["id"] for d in catalog["datasets"]],
                        }
                        for index, shop in enumerate(
                            (SHOP, "shopee-open-platform:1002", "lazada:1001")
                        )
                    },
                }
                config_path = temp / "mcp.json"
                config_path.write_text(json.dumps(mcp_config))
                mcp_env = env | {
                    "T10_MCP_CONFIG": str(config_path),
                    "T10_SOURCE_DSN": dsn("source_test"),
                    "T10_DERIVED_DSN": dsn("derived_test"),
                    "T10_PASSWORD": env["POSTGRES_PASSWORD"],
                    "PORT": urls["mcp"].rsplit(":", 1)[1],
                }
                command([mcp_python, "-c", MCP_SETUP], cwd=SERVICES / "shop-data-mcp", env=mcp_env)
                launch(
                    SERVICES / "shop-data-mcp",
                    mcp_python,
                    ["-c", MCP_SERVE],
                    mcp_env,
                    urls["mcp"],
                    "/health",
                )
                seed_fixture = json.loads(
                    (SERVICES / "mock-data-server/app/fixtures/mvp_base.json").read_text()
                )["shopee-open-platform"]
                projection_rows = json.loads(
                    command(
                        [mcp_python, "-c", PROJECTION_READ],
                        cwd=SERVICES / "shop-data-mcp",
                        env=mcp_env,
                    )
                )
                evidence["coverage"] = verify_complete_projection(seed_fixture, projection_rows)
                query_args = {"shop_key": SHOP, "query": "SELECT sku FROM agent_sku_catalog_v1"}
                own = mcp_call(urls["mcp"] + "/mcp", PHONE, "query_mart", query_args)
                assert not own.get("isError", False)
                own_data = own.get("structuredContent") or json.loads(own["content"][0]["text"])
                forbidden = mcp_call(
                    urls["mcp"] + "/mcp",
                    PHONE,
                    "query_mart",
                    query_args | {"shop_key": "shopee-open-platform:1002"},
                )
                assert forbidden["isError"]
                foreign = mcp_call(
                    urls["mcp"] + "/mcp",
                    "+84900000002",
                    "read_result",
                    {"shop_key": "shopee-open-platform:1002", "result_id": own_data["result_id"]},
                )
                assert foreign["isError"]
                evidence["mcp_http_isolation"] = True
                registry = json.loads((CORE / "config/registry.shop-data.example.json").read_text())
                for revision in registry["revisions"]:
                    revision["knowledge_mcp_url"] = urls["core"] + "/mcp/knowledge-memory"
                    revision["data_mcp_url"] = (
                        urls["mcp"] + "/mcp"
                        if revision["mcp_profile"] == "shop-data-read-v1"
                        else urls["core"] + "/mcp/data"
                    )
                registry_path = temp / "registry.json"
                registry_path.write_text(json.dumps(registry))
                core_env = process_env | {
                    "APP_ENV": "test",
                    "AGENT_PROVIDER": "fake",
                    "AUTH_MODE": "fixture",
                    "DATABASE_URL": f"sqlite:///{temp / 'core.db'}",
                    "CONFIG_PATH": str(registry_path),
                    "DATA_MCP_MODE": "remote",
                    "DATA_MCP_URL": urls["mcp"] + "/mcp",
                    "SHOP_DATA_MCP_URL": urls["mcp"] + "/mcp",
                    "SHOP_DATA_BINDINGS_PATH": str(CORE / "config/shop-data-bindings.example.json"),
                    "KNOWLEDGE_MEMORY_MCP_URL": urls["core"] + "/mcp/knowledge-memory",
                    "MCP_TOKEN_SIGNING_KEY": secrets.token_hex(32),
                    "T10_PROVIDER_STATE": str(temp / "provider-state"),
                }
                core = serve(
                    CORE,
                    sys.executable,
                    "tests.t10_loopback:app",
                    core_env,
                    urls["core"],
                    "/ready",
                )
                chat_env = process_env | {
                    "APP_ENV": "test",
                    "CHAT_BACKEND": "agent_core",
                    "SHOPOPS_API_URL": urls["source"],
                    "CHAT_AUTH_MODE": "demo_phone",
                    "AGENT_CORE_URL": urls["core"],
                    "AGENT_CORE_SHOP_ID": "shop-a",
                    "AGENT_CORE_CONFIG_REVISION": "returns-hosted-data-v1",
                    "CHAT_DATA_PATH": str(temp / "chat.db"),
                }
                chat = serve(
                    SERVICES / "shopops-chat-api",
                    chat_python,
                    "app.main:app",
                    chat_env,
                    urls["chat"],
                    "/health",
                )
                token = request(
                    urls["chat"] + "/api/chat/auth/demo-phone", {"phone_number": PHONE}
                )["access_token"]
                auth = {"Authorization": "Bearer " + token}
                fixture = json.loads(
                    (SERVICES / "mock-data-server/app/fixtures/mvp_base.json").read_text()
                )["shopee-open-platform"]

                # Pin the independently inspected synthetic coverage contract. This
                # assertion is not inferred from the first synchronized fact.
                configured = json.loads(
                    (CORE / "config/shop-data-bindings.example.json").read_text()
                )
                assert configured["bindings"][0]["coverage_start"] == "2026-10-17"
                assert oracle(fixture) == (
                    {"orders": 1, "returns": 0, "return_rate": 0.0},
                    {"orders": 3, "returns": 1, "return_rate": 33.333333},
                    {"negative_rating": 1, "sizing_mentions": 1},
                )

                def turn(key, mode="text"):
                    stream = request(
                        urls["chat"] + "/api/chat/messages",
                        {
                            "text": "SHIRT-M 2026-10-24 to 2026-10-30",
                            "client_message_id": key,
                            "output_mode": mode,
                        },
                        auth,
                        raw=True,
                    ).decode()
                    events = [
                        json.loads(line[6:])
                        for line in stream.splitlines()
                        if line.startswith("data: ")
                    ]
                    assert not any(e["type"] == "error" for e in events), events
                    message = next(e["message"] for e in events if e["type"] == "done")
                    assert message["kind"] == "answer", message
                    payload = json.loads(message["text"])
                    recent, baseline, categories = oracle(fixture)
                    metrics = payload["get_return_metrics"]
                    assert all(metrics[k] == v for k, v in recent.items()), (metrics, recent)
                    assert all(metrics["baseline"][k] == v for k, v in baseline.items())
                    review = payload["get_review_summary"]
                    for category in review["categories"]:
                        assert category["count"] == categories[category["category"]]
                    assert all("fixture:" not in s["reference"] for s in message["sources"])
                    assert PHONE not in json.dumps(message)
                    return message

                first = turn("report", "report")
                artifact = first["artifacts"][0]
                artifact_url = urls["chat"] + f"/api/chat/artifacts/{artifact['id']}/content"
                report = request(artifact_url, headers=auth, raw=True)
                assert hashlib.sha256(report).hexdigest() == artifact["sha256"]
                assert (
                    json.loads(report)["metrics"] == json.loads(first["text"])["get_return_metrics"]
                )
                denied(artifact_url, {}, status=401)
                for token in ("local-bob", "local-carol"):
                    denied(
                        urls["core"] + f"/api/v1/artifacts/{artifact['id']}/content",
                        {"Authorization": "Bearer " + token},
                    )
                turn("followup")
                assert request(urls["core"] + "/_fixture/stats") == {"sessions": 1, "turns": 2}
                # Restart the actual chat process over its persisted DB and Core session.
                chat.terminate()
                chat.wait(timeout=10)
                serve(
                    SERVICES / "shopops-chat-api",
                    chat_python,
                    "app.main:app",
                    chat_env,
                    urls["chat"],
                    "/health",
                )
                assert len(request(urls["chat"] + "/api/chat/messages", headers=auth)) == 4
                assert request(artifact_url, headers=auth, raw=True) == report
                turn("after-restart")
                core.terminate()
                core.wait(timeout=10)
                serve(
                    CORE,
                    sys.executable,
                    "tests.t10_loopback:app",
                    core_env,
                    urls["core"],
                    "/ready",
                )
                assert request(artifact_url, headers=auth, raw=True) == report
                turn("after-core-restart")
                assert request(urls["core"] + "/_fixture/stats")["sessions"] == 1
                # Create a new return in the disposable source through its real CRUD API.
                recent_ids = {
                    o["order_id"]
                    for o in fixture["orders"]
                    if "2026-10-24" <= o["ordered_at"][:10] <= "2026-10-30"
                    and o["status"] in {"shipped", "completed"}
                }
                sku_ids = {i["order_id"] for i in fixture["order_items"] if i["sku"] == "SHIRT-M"}
                candidate = sorted(
                    recent_ids & sku_ids - {r["order_id"] for r in fixture["returns"]}
                )[0]
                mutation = fixture["returns"][0] | {
                    "return_id": "T10-MUTATION",
                    "order_id": candidate,
                    "requested_at": "2026-10-30T14:00:00+07:00",
                }
                request(
                    urls["source"] + "/v1/entities/returns",
                    mutation,
                    {"X-Demo-User-Id": PHONE, "Idempotency-Key": uuid4().hex},
                )
                fixture["returns"].append(mutation)
                sync()
                changed = turn("mutation")
                assert (
                    json.loads(changed["text"])["get_return_metrics"]["returns"]
                    == json.loads(first["text"])["get_return_metrics"]["returns"] + 1
                )
                before_revisions = {
                    int(s["reference"].split(":revision:")[1].split(":")[0])
                    for s in first["sources"]
                    if s["type"] == "data"
                }
                after_revisions = {
                    int(s["reference"].split(":revision:")[1].split(":")[0])
                    for s in changed["sources"]
                    if s["type"] == "data"
                }
                assert len(before_revisions) == len(after_revisions) == 1
                assert next(iter(after_revisions)) == next(iter(before_revisions)) + 1
                denied(
                    urls["core"] + "/api/v1/shops/shop-a/orchestrator",
                    {"Authorization": "Bearer local-carol"},
                    {"template_id": "shopops", "config_revision": "returns-hosted-data-v1"},
                )
                # Revoke only the selected shop in the live source. The same phone
                # remains authorized for another configured shop, without a sync.
                command(
                    [
                        mcp_python,
                        "-c",
                        "import os,psycopg; "
                        "c=psycopg.connect(os.environ['T10_SOURCE_DSN']); "
                        'c.execute("UPDATE mock.shops SET deleted_at=now() '
                        "WHERE shop_key='shopee-open-platform:1001'\"); c.commit(); c.close()",
                    ],
                    cwd=SERVICES / "shop-data-mcp",
                    env=mcp_env,
                )
                revoked = mcp_call(urls["mcp"] + "/mcp", PHONE, "query_mart", query_args)
                assert revoked["isError"]
                remaining = mcp_call(
                    urls["mcp"] + "/mcp",
                    PHONE,
                    "query_mart",
                    query_args | {"shop_key": "lazada:1001"},
                )
                assert not remaining.get("isError", False)
                stream = request(
                    urls["chat"] + "/api/chat/messages",
                    {"text": "SHIRT-M 2026-10-24 to 2026-10-30", "client_message_id": "revoked"},
                    auth,
                    raw=True,
                ).decode()
                events = [
                    json.loads(line[6:])
                    for line in stream.splitlines()
                    if line.startswith("data: ")
                ]
                refusal = next(e["message"] for e in events if e["type"] == "done")
                assert refusal["kind"] == "cannot_answer"
                assert refusal["text"] == "permission_denied"
                assert not refusal.get("sources")
                evidence["live_selected_shop_revocation"] = True
                evidence.update(
                    passed=True,
                    oracle=True,
                    real_http=True,
                    report=True,
                    followup=True,
                    chat_restart=True,
                    core_restart=True,
                    mutation=True,
                    scope_rejection=True,
                )
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        if created:
            command(["docker", "rm", "--force", "--volumes", name])
        evidence["cleanup"] = all(p.poll() is not None for p in processes)
        rendered = json.dumps(evidence, sort_keys=True)
        Path("/tmp/t10-acceptance-evidence.json").write_text(rendered + "\n")
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
