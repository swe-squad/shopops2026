.PHONY: ci install run test lint format docker integration pipeline-integration check-config check-data config-schema catalog-schema
PYTHON ?= python3
VENV ?= .venv

# Run by .github/workflows/_ci.yml
ci: install lint test

install:
	test -x $(VENV)/bin/python || $(PYTHON) -m venv $(VENV)
	$(VENV)/bin/python -m pip install -r requirements-dev.txt

run:
	$(VENV)/bin/uvicorn app.main:create_app --factory --reload --port 8000

test:
	$(VENV)/bin/python -m pytest

lint:
	$(VENV)/bin/ruff check . && $(VENV)/bin/ruff format --check .

format:
	$(VENV)/bin/ruff check --fix . && $(VENV)/bin/ruff format .

integration:
	test -n "$(TEST_DATABASE_DSN)"
	$(VENV)/bin/python -m pytest tests/test_database.py -q

# Checkout PR #6 with its MCP bridge, or merge it first. See INTEGRATION.md.
pipeline-integration:
	$(VENV)/bin/python ../../scripts/test-data-mcp-integration.py --pipeline-root "$(PIPELINE_ROOT)" --pipeline-python "$(PIPELINE_PYTHON)"

check-config:
	$(VENV)/bin/python -m app.check

check-data:
	$(VENV)/bin/python -m app.check --connect

config-schema:
	@$(VENV)/bin/python -m app.check --schema config

catalog-schema:
	@$(VENV)/bin/python -m app.check --schema catalog

docker:
	docker build -t shop-data-mcp .
