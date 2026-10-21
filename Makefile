.PHONY: setup test lint format data eval-smoke

setup:
	cd backend && uv sync
	pre-commit install
	@if [ -f frontend/package.json ]; then cd frontend && pnpm install; fi

test:
	cd backend && uv run pytest
	@if [ -f frontend/package.json ]; then cd frontend && pnpm test --run; fi

lint:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src
	@if [ -f frontend/package.json ]; then cd frontend && pnpm lint; fi

format:
	cd backend && uv run ruff check --fix . && uv run ruff format .

data:
	@echo "No data scripts yet (Milestone 1: Wiktextract downloader)."

eval-smoke:
	@echo "Eval smoke test arrives in Milestone 3."
