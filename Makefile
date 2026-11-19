VENV := .vision-tools-env
PY := $(VENV)/bin/python3
RUFF := $(VENV)/bin/ruff
MYPY := $(VENV)/bin/mypy
PYTEST := $(VENV)/bin/pytest

.NOTPARALLEL:
.PHONY: setup lint format format-check typecheck test unit-test check clean serve smoke-test live-qa

## First-time setup: create venv and install all dependencies
setup:
	bash setup.sh

## Check production code, import boundaries and test assertions
lint:
	"$(RUFF)" check .
	"$(PY)" scripts/lint_tests.py tests

## Auto-format all Python files
format:
	"$(RUFF)" format .

format-check:
	"$(RUFF)" format --check .

## Run type checker (mypy --strict)
typecheck:
	"$(MYPY)" .

## Run test suite
test:
	"$(PYTEST)" -v --cov

## Run unit tests without the integration layer or coverage collection
unit-test:
	"$(PYTEST)" -m "not integration"

## Run full quality pipeline: lint + format-check + typecheck + test
check:
	bash lint.sh

## Remove build artifacts and caches
clean:
	find . -name .vision-tools-env -prune -o -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .mypy_cache .pytest_cache .ruff_cache *.egg-info dist build
	rm -f .coverage.vision-tools .coverage.vision-tools.*

## Start the MCP server (stdio transport)
serve:
	"$(PY)" server.py

## Quick smoke test (integration tests only)
smoke-test:
	"$(PYTEST)" -m integration -v --tb=short

## Generate test images for live MCP QA (see tests/live_qa_checklist.md)
live-qa:
	"$(PY)" tests/generate_live_images.py
