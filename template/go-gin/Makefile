.PHONY: ci run test lint build docker

# Run by .github/workflows/_ci.yml
ci: lint test build

run:
	go run ./cmd/server

test:
	go test -race ./...

lint:
	go vet ./...

build:
	CGO_ENABLED=0 go build -o bin/server ./cmd/server

docker:
	docker build -t __SERVICE_NAME__ .
