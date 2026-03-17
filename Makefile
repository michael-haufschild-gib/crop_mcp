VENV := $(HOME)/.vision-tools-env
PY := $(VENV)/bin/python3
RUFF := $(VENV)/bin/ruff
MYPY := $(VENV)/bin/mypy
PYTEST := $(VENV)/bin/pytest

.PHONY: setup lint format typecheck test check clean serve smoke-test

## First-time setup: create venv and install all dependencies
setup:
	bash setup.sh

## Run linter (ruff check)
lint:
	$(RUFF) check .

## Auto-format all Python files
format:
	$(RUFF) format .

## Run type checker (mypy --strict)
typecheck:
	$(MYPY) .

## Run test suite
test:
	$(PYTEST) -v

## Run full quality pipeline: lint + format-check + typecheck + test
check:
	bash lint.sh

## Remove build artifacts and caches
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .mypy_cache .pytest_cache .ruff_cache *.egg-info dist build

## Start the MCP server (stdio transport)
serve:
	$(PY) server.py

## Quick smoke test
smoke-test:
	$(PY) server.py --test
