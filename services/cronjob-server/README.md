# cronjob-server

Internal FastAPI processor and MCP-facing commerce API. See the approved
SPEC-data-pipeline.md and SPEC-sync-control.md at the repository root.
Container port 8000; local development uses port 8001 when both services run.

Use Python 3.14 and the standard make install/run/ci/docker targets under POSIX/WSL.
On Windows use the equivalent .venv/Scripts/python.exe commands.

Required runtime variables: POSTGRES_HOST, POSTGRES_USER, POSTGRES_PASSWORD,
POSTGRES_DB, and MOCK_DATA_SERVER_URL. POSTGRES_PORT defaults to 5432;
POSTGRES_SSLMODE defaults to prefer. SYNC_INTERVAL_SECONDS defaults to 0
(disabled); positive integers enable periodic full synchronization.
PORT defaults to 8000. See .env.example for placeholders.

The source URL is required and supplied at runtime. In CapRover use
http://srv-captain--mock-data-server-dev:8000 for dev, and
http://srv-captain--mock-data-server:8000 for production. Keep both services internal
with no public domain or port mapping. Never commit credentials.

Database tests use scripts/test_db.py and an isolated disposable PostgreSQL instance.
