# __SERVICE_NAME__

Go + Gin HTTP service. Entry point `cmd/server`, HTTP routing in `internal/server`. Listens on `$PORT` (default 8080).

## Commands

- Run: `make run`
- Test: `go test -race ./...`
- Lint: `go vet ./...`
- Build: `make build`, image: `make docker`

## Conventions

- Keep packages under `internal/`; `cmd/` only wires things together.
- Handlers return JSON via `c.JSON`; errors use a proper HTTP status, never 200 with an error body.
- Pass `context.Context` from the request (`c.Request.Context()`) into DB/HTTP calls.
- Tests: table-driven, `httptest` for handlers.

## Review guidelines (Go)

- Goroutines started per request without cancellation or with no way to stop.
- Ignored `err` return values, `panic` in request paths.
- Data races on shared state (maps, slices) accessed from handlers.
