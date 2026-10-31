"""Run real source -> cronjob -> PostgreSQL -> MCP tools using disposable local state.

Requires Docker, this service's dev venv, and the pipeline services' Python dependencies.
No deployment credentials or existing databases are read. The pipeline checkout must
include the MCP bridge migration/endpoints. Windows subprocesses have no visible window.
"""

import argparse
import json
import os
import secrets
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import URLError
from urllib.request import Request, urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
MCP = ROOT / "services/shop-data-mcp"


@contextmanager
def running_services(processes):
    try:
        yield
    finally:
        for process in reversed(processes):
            if os.name == "nt" and process.poll() is None:
                # Windows venv launchers may own a second Python process which inherits
                # the log handle. Terminate only this harness-created process tree.
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    capture_output=True,
                    check=True,
                )
                process.wait(timeout=10)
                continue
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def command(args: list[str], **kwargs) -> str:
    result = subprocess.run(args, capture_output=True, text=True, **kwargs)
    if result.returncode:
        raise RuntimeError(f"Test setup command failed: {args[:3]} (exit {result.returncode})")
    return result.stdout.strip()


def request(url: str, body: dict | None = None, headers: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = Request(url, data=data, headers={"Content-Type": "application/json", **(headers or {})})
    with urlopen(req, timeout=5) as response:
        return json.load(response)


def wait_ready(url: str) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            request(url + "/health/ready")
            return
        except (URLError, TimeoutError, ConnectionError):
            time.sleep(0.2)
    raise RuntimeError("Local test service did not become ready")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pipeline-root", type=Path, default=ROOT)
    parser.add_argument("--pipeline-python", type=Path, required=True)
    args = parser.parse_args()
    pipeline_root = args.pipeline_root.resolve()
    pipeline_python = str(args.pipeline_python.resolve())
    source = pipeline_root / "services/mock-data-server"
    cron = pipeline_root / "services/cronjob-server"
    if not (cron / "app/migrations/006_mcp_refreshes.sql").exists():
        parser.error("Pipeline checkout must contain the MCP bridge migration")
    name = "shop-mcp-e2e-" + uuid4().hex[:12]
    processes = []
    created = False
    env = os.environ.copy()
    env.update(
        POSTGRES_HOST="127.0.0.1",
        POSTGRES_USER="postgres",
        POSTGRES_PASSWORD=secrets.token_urlsafe(24),
        POSTGRES_DB="source_test",
        POSTGRES_SSLMODE="disable",
        SYNC_INTERVAL_SECONDS="0",
        MCP_SERVICE_TOKEN=secrets.token_urlsafe(32),
        MCP_SUBJECT_USERS_JSON=json.dumps({"agent-a": "+84900000001"}),
    )
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
        if not binding.startswith("127.0.0.1:"):
            raise RuntimeError("Test database must be bound to localhost")
        env["POSTGRES_PORT"] = binding.rsplit(":", 1)[1]
        deadline = time.monotonic() + 30
        while True:
            ready = subprocess.run(
                ["docker", "exec", name, "pg_isready", "-U", "postgres"],
                capture_output=True,
            )
            if ready.returncode == 0:
                break
            if time.monotonic() >= deadline:
                raise RuntimeError("Test database did not become ready")
            time.sleep(0.2)
        for database in ("derived_test", "control_test"):
            command(["docker", "exec", name, "createdb", "-U", "postgres", database])
        source_url = f"http://127.0.0.1:{free_port()}"
        cron_url = f"http://127.0.0.1:{free_port()}"
        env["MOCK_DATA_SERVER_URL"] = source_url
        with (
            TemporaryDirectory(prefix="shop-mcp-e2e-", dir=MCP) as temporary,
            running_services(processes),
        ):
            with open(Path(temporary) / "services.log", "w", encoding="utf-8") as log:
                for directory, database, url in (
                    (source, "source_test", source_url),
                    (cron, "derived_test", cron_url),
                ):
                    service_env = env | {"POSTGRES_DB": database}
                    command(
                        [pipeline_python, "-m", "app.cli", "migrate"],
                        cwd=directory,
                        env=service_env,
                    )
                    if directory == source:
                        command(
                            [pipeline_python, "-m", "app.cli", "seed"],
                            cwd=directory,
                            env=service_env,
                        )
                    processes.append(
                        subprocess.Popen(
                            [
                                pipeline_python,
                                "-m",
                                "uvicorn",
                                "app.main:app",
                                "--host",
                                "127.0.0.1",
                                "--port",
                                url.rsplit(":", 1)[1],
                                "--no-access-log",
                            ],
                            cwd=directory,
                            env=service_env,
                            stdout=log,
                            stderr=log,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                        )
                    )
                    wait_ready(url)
                # Bootstrap the initial snapshot before creating shop-bound query logins.
                headers = {"X-Demo-User-Id": "+84900000001", "Idempotency-Key": "bootstrap"}
                run = request(cron_url + "/v1/sync-runs", {}, headers)
                deadline = time.monotonic() + 30
                while True:
                    state = request(cron_url + run["status_url"], headers=headers)
                    if state["status"] == "succeeded":
                        break
                    if state["status"] == "failed" or time.monotonic() >= deadline:
                        raise RuntimeError("Initial snapshot publication failed")
                    time.sleep(0.2)

                # Test-only DSNs; production Settings.load still requires verified TLS.
                def dsn(database: str) -> str:
                    return (
                        f"host=127.0.0.1 port={env['POSTGRES_PORT']} dbname={database} "
                        f"user=postgres password={env['POSTGRES_PASSWORD']} sslmode=disable"
                    )

                test_env = env | {
                    "MCP_PIPELINE_TEST_DSN": dsn("derived_test"),
                    "MCP_CONTROL_TEST_DSN": dsn("control_test"),
                    "MCP_CRONJOB_TEST_URL": cron_url,
                    "MCP_MOCK_TEST_URL": source_url,
                    "MCP_CRONJOB_TEST_TOKEN": env["MCP_SERVICE_TOKEN"],
                }
                runner = (
                    "import asyncio,sys,pytest; "
                    "asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy()) "
                    "if sys.platform == 'win32' else None; "
                    "raise SystemExit(pytest.main("
                    "['tests/test_live_pipeline.py','-q','-p','no:cacheprovider']))"
                )
                return subprocess.call([sys.executable, "-c", runner], cwd=MCP, env=test_env)
    except (RuntimeError, OSError, URLError) as exc:
        diagnostic = str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__
        print(
            f"Integration setup failed ({diagnostic}, "
            f"OS code {getattr(exc, 'winerror', None)}); "
            "check Docker, pipeline checkout and Python dependencies",
            file=sys.stderr,
        )
        return 1
    finally:
        if created:
            subprocess.run(["docker", "rm", "--force", name], capture_output=True, check=True)


if __name__ == "__main__":
    raise SystemExit(main())
