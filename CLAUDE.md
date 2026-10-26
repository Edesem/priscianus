# Rules for AI agents in this repo

## Where agents work
`src/backend/priscianus/api/`, `src/backend/priscianus/llm/`, `src/frontend/`, CI, Docker, docs, always through PRs the owner reviews.

## Commands
- `make setup`: install deps and git hooks
- `make dev`: run backend (:8000) and frontend (:5173) together; `make backend` / `make frontend` run one
- `make test`: pytest (with coverage) and frontend tests
- `make lint`: ruff, ruff format check, mypy (strict on morphology/ and verifier/), frontend lint
- `make format`: auto-fix Python

## Conventions
- Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`); one PR closes one issue.
- Never commit `.env`, API keys, or raw data under `src/data/raw/`.
- Data licences: see `DATA_LICENCES.md`. Do not commit UD treebanks (CC BY-NC-SA).
- Plan: `docs/plan.md`. Decisions: `docs/adr/`.

## Layout
All code lives under `src/` (`backend/`, `evals/`, `data/`, `frontend/`). The repo root holds only config, docs and project files.
