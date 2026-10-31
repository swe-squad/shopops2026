"""Run both service images on an isolated, disposable Docker network."""

import argparse
import http.client
import os
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


def command(args, *, env=None):
    result = subprocess.run(
        args, check=False, cwd=ROOT, env=env, capture_output=True, text=True
    )
    if result.returncode:
        # Do not print commands/env: credentials are passed only by environment name.
        raise RuntimeError(
            f"Container command failed: {args[0:2]} (exit {result.returncode})"
        )
    return result.stdout.strip()


def ready(url):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url + "/health/ready", timeout=2) as response:
                if response.status == 200:
                    return
        except (
            urllib.error.URLError,
            TimeoutError,
            ConnectionError,
            http.client.HTTPException,
        ):
            pass
        time.sleep(0.2)
    raise RuntimeError("Service did not become ready")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=["crud", "recovery", "all"], default="all")
    parser.add_argument("--no-build", action="store_true")
    args = parser.parse_args()
    tag = "shopops-pair-" + uuid.uuid4().hex
    network, names = tag, []
    env = os.environ.copy()
    env.update(
        POSTGRES_HOST="postgres",
        POSTGRES_PORT="5432",
        POSTGRES_USER="shopops_test",
        POSTGRES_PASSWORD=secrets.token_urlsafe(24),
        POSTGRES_DB="shopops_test_" + uuid.uuid4().hex,
        POSTGRES_SSLMODE="disable",
        MOCK_DATA_SERVER_URL="http://proxy:8000",
        SYNC_INTERVAL_SECONDS="0",
    )
    env_args = [
        part
        for name in (
            "POSTGRES_HOST",
            "POSTGRES_PORT",
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
            "POSTGRES_DB",
            "POSTGRES_SSLMODE",
            "MOCK_DATA_SERVER_URL",
            "SYNC_INTERVAL_SECONDS",
        )
        for part in ("-e", name)
    ]
    created_network = False
    try:
        if not args.no_build:
            for service in ("mock-data-server", "cronjob-server"):
                print(f"Building {service}", flush=True)
                command(
                    [
                        "docker",
                        "build",
                        "-t",
                        f"shopops-{service}:dev",
                        str(ROOT / "services" / service),
                    ]
                )
        command(
            ["docker", "network", "create", "--label", "shopops.test=true", network]
        )
        created_network = True
        db_name = tag + "-db"
        command(
            [
                "docker",
                "run",
                "-d",
                "--name",
                db_name,
                "--network",
                network,
                "--network-alias",
                "postgres",
                *env_args,
                "postgres:17-alpine",
            ],
            env=env,
        )
        names.append(db_name)
        deadline = time.monotonic() + 45
        while True:
            result = subprocess.run(
                ["docker", "exec", db_name, "pg_isready", "-U", "shopops_test"],
                capture_output=True,
                check=False,
            )
            if result.returncode == 0:
                break
            if time.monotonic() >= deadline:
                raise RuntimeError("Test PostgreSQL did not start")
            time.sleep(0.2)
        urls = {}
        for service, alias in (
            ("mock-data-server", "source"),
            ("cronjob-server", "processor"),
        ):
            if alias == "processor":
                proxy_name = tag + "-proxy"
                proxy_file = ROOT / "services/cronjob-server/tests/e2e/proxy.py"
                command(
                    [
                        "docker",
                        "run",
                        "-d",
                        "--name",
                        proxy_name,
                        "--network",
                        network,
                        "--network-alias",
                        "proxy",
                        "-p",
                        "127.0.0.1::8000",
                        "--mount",
                        f"type=bind,source={proxy_file},target=/proxy.py,readonly",
                        "shopops-cronjob-server:dev",
                        "python",
                        "/proxy.py",
                    ]
                )
                names.append(proxy_name)
                deadline = time.monotonic() + 15
                while True:
                    binding = command(["docker", "port", proxy_name, "8000/tcp"])
                    if binding.startswith("127.0.0.1:"):
                        break
                    if time.monotonic() >= deadline:
                        raise RuntimeError("Proxy port was not published")
                    time.sleep(0.2)
                urls["proxy"] = "http://" + binding
                ready(urls["proxy"])
            image = f"shopops-{service}:dev"
            common = ["docker", "run", "--rm", "--network", network, *env_args, image]
            command([*common, "python", "-m", "app.cli", "migrate"], env=env)
            if alias == "source":
                command(
                    [*common, "python", "-m", "app.cli", "seed", "--profile", "mvp"],
                    env=env,
                )
            name = tag + "-" + alias
            command(
                [
                    "docker",
                    "run",
                    "-d",
                    "--name",
                    name,
                    "--network",
                    network,
                    "--network-alias",
                    alias,
                    "-p",
                    "127.0.0.1::8000",
                    *env_args,
                    image,
                ],
                env=env,
            )
            names.append(name)
            deadline = time.monotonic() + 15
            while True:
                binding = command(["docker", "port", name, "8000/tcp"])
                if binding.startswith("127.0.0.1:"):
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeError("Container port was not published")
                time.sleep(0.2)
            urls[alias] = "http://" + binding
            ready(urls[alias])
        test_env = env | {
            "PAIR_SOURCE_URL": urls["source"],
            "PAIR_PROCESSOR_URL": urls["processor"],
            "PAIR_PROXY_URL": urls["proxy"],
            "PAIR_SOURCE_CONTAINER": tag + "-source",
            "PAIR_PROCESSOR_CONTAINER": tag + "-processor",
            "PAIR_DB_CONTAINER": db_name,
            "PAIR_NETWORK": network,
        }
        python = (
            ROOT
            / "services/cronjob-server/.venv"
            / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        )
        executable = str(python) if python.exists() else sys.executable
        files = (
            ["test_crud.py", "test_recovery.py"]
            if args.suite == "all"
            else [f"test_{args.suite}.py"]
        )
        paths = [
            str(ROOT / "services/cronjob-server/tests/e2e" / file) for file in files
        ]
        with TemporaryDirectory(prefix="shopops-pair-cache-") as cache:
            return subprocess.call(
                [executable, "-m", "pytest", *paths, "-q", "-o", f"cache_dir={cache}"],
                cwd=ROOT,
                env=test_env,
            )
    finally:
        for name in reversed(names):
            command(["docker", "rm", "-f", name])
        if created_network:
            command(["docker", "network", "rm", network])


if __name__ == "__main__":
    raise SystemExit(main())
