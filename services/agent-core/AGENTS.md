# agent-core

Python FastAPI service. App factory in `app/main.py`, tests in `tests/`. Listens on `$PORT` (default 8000).

## Commands

- Setup: `make install` (creates `.venv`)
- Run: `make run`
- Test: `.venv/bin/pytest`
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

## Agent Core ownership and verification

- Follow the spec and task tracker in this service. Shared contracts are in app/contracts/.
- T01 owns scaffolding, config, storage, worker, app wiring and shared fixtures; T02/T03/T04 own their
  modules. Preserve other owners' edits. Request shared contract/dependency changes from T01.
- All implementation/config/docs/scripts must stay under services/agent-core/; root workflows,
  templates, scripts and unrelated services are read-only for these tasks.
- One SQLite database owner, one application worker, one replica; do not automatically resubmit
  unknown provider mutations or unlock unresolved conversations.
- Default tests are offline except loopback. Do not expose secrets, prompts, outputs, tool payloads
  or identity in logs. Never copy another worktree's runtime environment.
- Run make ci and the task's scoped tests. Docker volume persistence and live acceptance need separate
  recorded evidence; passing fakes or image builds do not establish those acceptance criteria.
