.PHONY: ci install run test lint format docker

# Run by .github/workflows/_ci.yml
ci: install lint test

install:
	python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt

run:
	.venv/bin/uvicorn app.main:app --reload --port 8000

test:
	.venv/bin/pytest

lint:
	.venv/bin/ruff check . && .venv/bin/ruff format --check .

format:
	.venv/bin/ruff check --fix . && .venv/bin/ruff format .

docker:
	docker build -t agent-core .
