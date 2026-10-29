.PHONY: help setup dev backend frontend build test test-backend test-evals test-frontend lint format clean data eval-data eval eval-smoke parse
.DEFAULT_GOAL := help

BACKEND_PORT ?= 8000
FRONTEND_PORT ?= 5173

help: ## List available commands
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

setup: ## Install deps and git hooks
	cd src/backend && uv sync
	cd src/evals && uv sync
	pre-commit install
	@if [ -f src/frontend/package.json ]; then cd src/frontend && pnpm install; fi

dev: ## Run backend and frontend together (Ctrl-C stops both)
	@$(MAKE) -j2 --no-print-directory backend frontend

backend: ## Run the API with auto-reload on BACKEND_PORT (default 8000)
	cd src/backend && uv run uvicorn priscianus.api.main:app --reload --port $(BACKEND_PORT)

frontend: ## Run the Vite dev server on FRONTEND_PORT (default 5173)
	cd src/frontend && pnpm dev --port $(FRONTEND_PORT)

build: ## Build the frontend for production
	cd src/frontend && pnpm build

test: test-backend test-evals test-frontend ## Run all tests

test-backend: ## Run pytest with coverage
	cd src/backend && uv run pytest

test-evals: ## Run the evals' pytest with coverage
	cd src/evals && uv run pytest

test-frontend: ## Run frontend tests once
	@if [ -f src/frontend/package.json ]; then cd src/frontend && pnpm test --run; fi

lint: ## Run ruff, mypy and frontend lint
	cd src/backend && uv run ruff check . && uv run ruff format --check . && uv run mypy priscianus
	cd src/evals && uv run ruff check . && uv run ruff format --check . && uv run mypy evals
	@if [ -f src/frontend/package.json ]; then cd src/frontend && pnpm lint; fi

format: ## Auto-fix Python
	cd src/backend && uv run ruff check --fix . && uv run ruff format .
	cd src/evals && uv run ruff check --fix . && uv run ruff format .

clean: ## Remove caches and build output
	find src \( -name node_modules -o -name .venv \) -prune -o -type d \( -name __pycache__ -o -name .pytest_cache -o -name .mypy_cache -o -name .ruff_cache \) -prune -exec rm -rf {} +
	rm -f src/backend/.coverage
	rm -rf src/frontend/dist

data: ## Download raw data into src/data/raw/, then build src/data/morphology.db
	cd src/backend && uv run python ../data/scripts/download_wiktextract.py
	cd src/backend && uv run python -m priscianus.morphology.build_index

eval-data: ## Download the UD Latin treebanks (pinned r2.18) into src/data/raw/ud/
	cd src/backend && uv run python ../data/scripts/download_ud_latin.py

eval: ## Run an eval, e.g. make eval ARGS="run --mode raw --set parse --split dev --limit 20"
	cd src/evals && uv run python -m evals $(ARGS)

eval-smoke: ## Run the eval smoke test (not yet implemented)
	@echo "The CI smoke eval arrives in Milestone 4 (docs/plan.md, section 5)."

parse: ## Parse a Latin word, e.g. make parse WORD=amabat (needs make data)
	@test -n "$(WORD)" || { echo "Usage: make parse WORD=amabat"; exit 1; }
	cd src/backend && uv run python -m priscianus.morphology parse $(WORD)
