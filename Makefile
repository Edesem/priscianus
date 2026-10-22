.PHONY: setup test lint format data eval-smoke

setup:
	cd src/backend && uv sync
	pre-commit install
	@if [ -f src/frontend/package.json ]; then cd src/frontend && pnpm install; fi

test:
	cd src/backend && uv run pytest
	@if [ -f src/frontend/package.json ]; then cd src/frontend && pnpm test --run; fi

lint:
	cd src/backend && uv run ruff check . && uv run ruff format --check . && uv run mypy priscianus
	@if [ -f src/frontend/package.json ]; then cd src/frontend && pnpm lint; fi

format:
	cd src/backend && uv run ruff check --fix . && uv run ruff format .

data:
	@echo "No data scripts yet (Milestone 1: Wiktextract downloader)."

eval-smoke:
	@echo "Eval smoke test arrives in Milestone 3."
