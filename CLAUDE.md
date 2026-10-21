# Rules for AI agents in this repo

## Hand-written zones: do not write code here
- `backend/src/latin_tutor/morphology/`
- `backend/src/latin_tutor/verifier/`
- `evals/`

Agents may explain, review and suggest in these areas, but must not create or edit code there.

## Where agents work
`backend/src/latin_tutor/api/`, `backend/src/latin_tutor/llm/`, `frontend/`, CI, Docker, docs, always through PRs the owner reviews.

## Commands
- `make setup`: install deps and git hooks
- `make test`: pytest (with coverage) and frontend tests
- `make lint`: ruff, ruff format check, mypy (strict on morphology/ and verifier/), frontend lint
- `make format`: auto-fix Python

## Conventions
- Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`); one PR closes one issue.
- Never commit `.env`, API keys, or raw data under `data/raw/`.
- Data licences: see `DATA_LICENCES.md`. Do not commit UD treebanks (CC BY-NC-SA).
- Plan: `docs/plan.md`. Decisions: `docs/adr/`.
