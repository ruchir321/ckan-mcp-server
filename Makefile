.PHONY: help sync lint format-check test check docker-build

help:
	@echo "sync          Install locked dependencies"
	@echo "lint          Run Ruff lint checks"
	@echo "format-check  Verify Ruff formatting"
	@echo "test          Run the offline test suite"
	@echo "check         Run lint, formatting, and tests"
	@echo "docker-build  Build the production image"

sync:
	uv sync --all-extras --frozen

lint:
	uv run ruff check .

format-check:
	uv run ruff format --check .

test:
	uv run pytest -q

check: lint format-check test

docker-build:
	docker build -t ckan-mcp-server .
