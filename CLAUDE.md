# Rules for AI agents in this repo

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

# Working with me on this project

I'm the sole developer. I'm a junior engineer, and I'm still learning this codebase.
I review every PR myself, so your job is to keep my reviewing effort low
and make sure I understand what changed.

## How to communicate
- Write in plain English. If you use a technical term, explain it in one short sentence the first time.
- Lead with what the change does for the user or the app, then explain how.
- Keep explanations short. Use concrete examples ("when a student types X, the tutor now does Y") rather than abstract descriptions.
- If you're unsure about something or made an assumption, say so plainly instead of hiding it.

## Scope of each issue
- Implement only what the issue asks for. Don't add extra features, refactors or abstractions "for later."
- Keep PRs small. If an issue needs more than roughly 300 changed lines, stop and propose splitting it.
- Prefer simple, readable code over clever code. I'd rather see repetition than an abstraction I can't follow.

## Tests
- Add at most 5–8 tests per PR unless you explain why more are needed.
- Test behaviour that matters to the user or to correctness, not implementation details, trivial getters or mock wiring.
- Prefer a few integration tests over many tiny unit tests.
- Don't add a test that duplicates an existing one.

## PR description (required, in this format)

### What this does
3–5 plain-English bullets. No jargon.

### Why
One or two sentences linking back to the issue.

### How to check it yourself
Exact steps to try it in the running app: what to click or type, and what I should see.

### Tests added
One line per test in plain English, e.g. "rejects an empty translation", "flags a wrong case ending on a 3rd-declension noun."

### Look closely at
The 1–3 places where a mistake would matter most (prompt building, answer assessment, data model, API keys or cost), with a short note on why. If nothing is risky, say "Nothing risky — mostly wiring/UI."

### Assumptions and open questions
Anything you guessed or weren't sure about.

## When I ask "explain this"
Explain it as if I'll be the one maintaining it: what it's for, how data flows through it step by step, and what would break if it were removed. Use plain English and a small example.