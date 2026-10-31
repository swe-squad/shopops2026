# Data and tool changes

Start here when extending the MCP. [README.md](README.md) owns deployment and database setup;
[HANDOFF.md](HANDOFF.md) owns the contracts with identity, approval and collection engineers.
The service is configurable before those external services exist; unavailable integrations
remain denied. Configuration changes require a process restart. Python changes require a
new image deployment.

## Choose the smallest change

| Task | Edit | Verify |
|---|---|---|
| Register a mart or sanitized raw view | Dataset entry in the catalog | Config check, database preflight, query as the intended shop |
| Explain a metric, grain, joins or freshness | Dataset `description` and `semantics` | Discover/describe it through the agent |
| Allow a shop to use a dataset | Operator's `shops` mapping plus PostgreSQL grants/policies | Two-shop isolation; catalog edits alone do not authorize access |
| Change a tool's input, description or output | Decorated function in [app/server.py](app/server.py) | SDK tests in [tests/test_protocol.py](tests/test_protocol.py) |
| Change analytical workflows | [app/service.py](app/service.py) | [tests/test_service.py](tests/test_service.py) |
| Support another SQL expression | [app/query.py](app/query.py) | SQL restriction tests and disposable PostgreSQL checks |
| Change upstream request/response contracts | [app/upstream.py](app/upstream.py), [app/responses.py](app/responses.py) and owning service | Update HANDOFF and adapter/response tests together |

New tables normally use the existing discovery and query tools. Add a domain-specific tool
when it packages a recurring operation with a clearer contract for the agent.

## Edit the catalog independently of secrets

Use [catalog.example.json](catalog.example.json) as the non-secret dataset file and
[config.example.json](config.example.json) as the operator's runtime template. Set both
paths from [.env.example](.env.example) in the process environment or CapRover App Configs;
the app does not automatically source a dotenv file. Mount the files at those paths.
Keep the populated runtime file outside Git because it contains database and service
credentials. The catalog may be reviewed in Git only when its metadata is approved for
that repository's audience; never put secrets or customer records in descriptions.

The catalog owns dataset definitions. The operator's runtime file owns credentials,
shop allowlists and budgets. The catalog cannot set those fields. Existing deployments
may keep `datasets` inline in `MCP_CONFIG_FILE`; choose one source. Setting
`MCP_CATALOG_FILE` while also declaring inline `datasets` is rejected to prevent a silent
override.

For a new dataset:

1. Have the database owner publish the table or sanitized view and enforce shop isolation.
2. Add its logical ID, physical relation and approved columns to the catalog. Use
   `semantics` for the business definition, grain, currency, timezone, safe joins, missing
   value rules and freshness source. Populate real metadata; example watermarks are not
   live measurements. Raw datasets need an approved `time_column` for bounded grants.
3. Ask the operator to add that ID to the intended shop's allowlist and provision the
   corresponding database permissions. A new catalog entry is not a grant of access.
4. Run the commands below, restart with the changed catalog, and exercise discovery and
   a bounded query as the intended shop. Confirm another shop cannot see the data.

The Python models in [app/settings.py](app/settings.py) are the executable contract.
Generate editor schemas directly from those models, without credentials or a database:

```sh
make install
make config-schema > /tmp/shop-data-mcp-config.schema.json
make catalog-schema > /tmp/shop-data-mcp-catalog.schema.json
make check-config
make check-data
```

Associate the exported schema with its matching JSON file in your editor. Do not add
editor-only keys such as `$schema` to runtime files: unknown keys are rejected. The schema
checks field shapes; `check-config` also checks cross-file dataset mappings. `check-data`
checks control storage and configured published mart columns. It does not certify RLS,
raw grants or upstream behavior. Those need the real integration checks in README.

## Modify or add a tool

The registration point is `build_server` in [app/server.py](app/server.py). Keep tool
functions thin: use type hints for inputs and structured output, describe when the agent
should call the tool, and delegate analytical work to `DataService`. Keep existing public
names/parameters compatible unless all consumers are intentionally updated.

For example, this function can be registered **inside `build_server`, before its return**
to package a recurring order count using the configured `order_economics` dataset:

```python
@server.tool(structured_output=True, annotations=read)
async def summarize_orders(shop_key: str | None = None) -> dict[str, Any]:
    """Count the current shop's orders using the configured order-grain dataset."""
    return await run(
        service.analyze,
        select(shop_key),
        "SELECT count(*) AS order_count FROM order_economics",
    )
```

The example deliberately uses the existing authorization, query projection, limits and
result-storage path. Decide the correct counting grain from the catalog before publishing
it. An annotation describes behavior; it does not enforce permissions. For new operations,
enforce the required scope in the service method. For tools accepting values, build SQL
through the existing validated AST path or bound values; never concatenate user input.

Do not call source tables through the control connection, trust a shop argument without checking current membership, skip raw grant checks, or execute a model query with migration/writer privileges.
Keep these safeguards in the shared service/database layers so future tools reuse them.

Verify the change with the owning tests, then `make ci`. The SDK tests exercise actual tool
listing and calls, so add a call for the new tool plus an invalid/unauthorized case. For a
behavior change that touches SQL or storage, use the disposable database checks documented
in README. They must never target the operational database. Update HANDOFF only if an
external service contract changes.
