# mock-data-server

Internal FastAPI commerce mock. See the root SPEC-mock-source.md for the approved
contract. Container port: 8000. Python 3.14; use `make install`, `make run`,
`make ci`, and `make docker` under POSIX/WSL. Native Windows uses the equivalent
`.venv/Scripts/python.exe -m pytest` and `-m ruff` commands.

Runtime configuration is provided by the environment. Never commit `.env` or
credentials. This service is internal in CapRover, with no public domain or port
mapping. The processor reaches it through `MOCK_DATA_SERVER_URL`.

| Variable | Meaning |
|---|---|
| POSTGRES_HOST | Required database host |
| POSTGRES_PORT | Port, default 5432 |
| POSTGRES_USER | Required username |
| POSTGRES_PASSWORD | Required secret |
| POSTGRES_DB | Required database name |
| POSTGRES_SSLMODE | PostgreSQL TLS policy, default prefer |
| PORT | HTTP port, default 8000 |

Database tests will run only against an explicitly isolated test database.
