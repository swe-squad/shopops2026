# cronjob-server

Python FastAPI service. App factory in `app/main.py`, tests in `tests/`. Listens on `$PORT` (default 8000).

## Commands

- Setup: `make install` (creates `.venv`)
- Run: `make run`
- Test: `make test` (Docker-backed isolated PostgreSQL; never use the demo database)
- Lint/format: `make lint` / `make format` (ruff)

## Conventions

- Dependencies pinned in `requirements.txt` (runtime) and `requirements-dev.txt` (dev/test).
- Request/response bodies use Pydantic models, not raw dicts, for anything beyond trivial endpoints.
- Type hints on all functions.
- Tests use `fastapi.testclient.TestClient`.

## Review guidelines (FastAPI)

- Blocking I/O (sync DB/HTTP clients, `time.sleep`) inside `async def` endpoints.
- Missing Pydantic validation, or `response_model` that leaks internal fields.
- Unpinned or added-but-unused dependencies in the requirements files.

## Data-service checks

- Run explicit migrations before startup; source seeding is explicit and must preserve edits.
- Keep all fixtures/migrations required at runtime under `app/` for service-only Docker builds.
- Cross-service calls use HTTP through runtime configuration; never import sibling service code.
- Preserve idempotency, current membership checks, composite keys, and historical raw evidence.
- Run the root pair harness after changing shared HTTP contracts.
