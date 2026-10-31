"""Run tests using a disposable, locally bound PostgreSQL container."""

import os
import secrets
import subprocess
import sys
import time
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory

import psycopg

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    name = "shopops-test-" + uuid.uuid4().hex
    env = os.environ.copy()
    # Never inherit application connection settings for test setup or cleanup.
    env.update(
        POSTGRES_HOST="127.0.0.1",
        POSTGRES_USER="shopops_test",
        POSTGRES_PASSWORD=secrets.token_urlsafe(24),
        POSTGRES_DB="shopops_test_" + uuid.uuid4().hex,
        POSTGRES_SSLMODE="disable",
        SHOP_OPS_TEST_DATABASE="1",
    )
    created = False
    try:
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-d",
                "--name",
                name,
                "--label",
                "shopops.test=true",
                "-p",
                "127.0.0.1::5432",
                "-e",
                "POSTGRES_USER",
                "-e",
                "POSTGRES_PASSWORD",
                "-e",
                "POSTGRES_DB",
                "postgres:17-alpine",
            ],
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )
        created = bool(result.stdout.strip())
        deadline = time.monotonic() + 15
        while True:
            binding = subprocess.check_output(
                ["docker", "port", name, "5432/tcp"], text=True
            ).strip()
            if binding.startswith("127.0.0.1:"):
                break
            if time.monotonic() >= deadline:
                raise RuntimeError("Docker did not publish the test PostgreSQL port")
            time.sleep(0.2)
        env["POSTGRES_PORT"] = binding.rsplit(":", 1)[1]
        deadline = time.monotonic() + 45
        while True:
            try:
                with psycopg.connect(
                    host=env["POSTGRES_HOST"],
                    port=env["POSTGRES_PORT"],
                    user=env["POSTGRES_USER"],
                    password=env["POSTGRES_PASSWORD"],
                    dbname=env["POSTGRES_DB"],
                    connect_timeout=2,
                ) as conn:
                    conn.execute("SELECT 1")
                break
            except psycopg.OperationalError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("Test PostgreSQL did not become ready") from None
                time.sleep(0.2)
        args = sys.argv[1:] or ["tests", "-q"]
        with TemporaryDirectory(prefix="shopops-pytest-") as cache:
            return subprocess.call(
                [sys.executable, "-m", "pytest", "-o", f"cache_dir={cache}", *args],
                cwd=ROOT,
                env=env,
            )
    except subprocess.CalledProcessError as exc:
        print(
            f"Test container operation failed (exit {exc.returncode}); check Docker.",
            file=sys.stderr,
        )
        return 1
    finally:
        if created:
            subprocess.run(["docker", "rm", "-f", name], capture_output=True, check=True)


if __name__ == "__main__":
    raise SystemExit(main())
