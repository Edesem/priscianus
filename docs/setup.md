# Day-one setup: Priscianus

How to take [plan.md](plan.md) into your IDE and run it like a professional project from the first commit. Defaults are picked where there's a choice; change any of them freely.

---

## 1. Create the repo (today, ~30 minutes)

1. On GitHub, create **`priscianus`** under your account (`Edesem`). **Public**, with a README, a `.gitignore` for Python, and the **MIT** licence.
2. Clone it locally and open it in VS Code.
3. Attach it to this project in **Project settings → Resources** so Claude can work on it with you (scaffolding, reviews, CI fixes).
4. Copy `plan.md` into the repo as `docs/plan.md`. The plan lives with the code from now on.

---

## 2. Open source? Yes, from day one

- **Why:** recruiters can read the code, the eval results are verifiable, and a public commit history shows how you work. This matters more than any line on a CV.
- **Code licence: MIT.** Simple and permissive. Open code doesn't stop a paid hosted version later: people pay for the service, not the source.
- **Data is licensed separately**, and this is the part to get right:
  - The morphology index built from Wiktionary is **CC BY-SA 4.0**. If you publish the built database, it must be CC BY-SA too, with attribution.
  - Several Universal Dependencies treebanks are **non-commercial (CC BY-NC-SA)**. Don't commit them; have a script download them, and keep them out of anything you charge for.
  - Record all of this in `DATA_LICENCES.md`.
- **Never commit** raw data dumps, `.env` files or API keys. Turn on GitHub secret scanning and push protection.
- **Before charging money**, check your employer's rules on outside work. Defence usually has a secondary-employment policy. Publishing open-source code is normally fine, but a paid product may need a declaration. *(This is general advice; check your own conditions.)*

---

## 3. Repo layout

A single repo holding the backend, evals and front end.

```
priscianus/
├── backend/
│   ├── pyproject.toml
│   ├── src/priscianus/
│   │   ├── morphology/     # index, normaliser, lookup
│   │   ├── verifier/       # claim checking, repair loop
│   │   ├── llm/            # Claude client, prompts, tools
│   │   └── api/            # FastAPI routes
│   └── tests/
├── evals/                  # datasets, runners, reports
├── data/
│   ├── scripts/            # build the index: `make data`
│   └── raw/                # gitignored downloads
├── frontend/               # Vite + React + TS
├── docs/
│   ├── plan.md
│   └── adr/                # architecture decision records
├── .github/
│   ├── workflows/ci.yml
│   ├── dependabot.yml
│   ├── pull_request_template.md
│   └── ISSUE_TEMPLATE/
├── CLAUDE.md               # rules for AI agents in this repo
├── Makefile                # one command for each task
├── .env.example
├── .pre-commit-config.yaml
├── README.md · LICENSE · DATA_LICENCES.md · CONTRIBUTING.md
```

---

## 4. Tooling

| Area | Choice |
|---|---|
| Python env and deps | **uv** (fast, one lockfile) and Python 3.12 |
| Python quality | **ruff** (lint + format), **mypy --strict** on `morphology/` and `verifier/`, **pytest** + coverage |
| Front end | **pnpm**, Vite, ESLint, Prettier, Vitest, React Testing Library |
| Task runner | `Makefile` with `make setup`, `make test`, `make lint`, `make data`, `make eval-smoke` |
| Git hooks | **pre-commit** running ruff, prettier and a secrets check before every commit |
| IDE | VS Code with the Python, Ruff, ESLint and Prettier extensions, plus Claude Code in the terminal |
| Secrets | `.env` (gitignored) holding `ANTHROPIC_API_KEY`; `.env.example` documents it; a GitHub Actions secret for CI |

---

## 5. Professional habits from commit one

- **Protect `main`.** All changes go through pull requests, even working alone, and CI must pass before you merge. Your PR history becomes a portfolio of its own.
- **Make each milestone a GitHub Milestone**, with issues for the tasks under it and a GitHub Projects board. Each PR closes an issue.
- **Use Conventional Commits** (`feat:`, `fix:`, `test:`, `docs:`) so you can generate a changelog. Tag a release (`v0.1.0`) at the end of each milestone.
- **Write ADRs** for the big decisions, one short page each: "SQLite for the morphology index", "UD feature names as the internal schema", "Haiku 5.5 + verifier as the default". Interviewers love asking "why did you choose X?".
- **Write tests first for the checker.** The normaliser and the verifier are pure functions with clear right answers, so they suit TDD.
- **Fill in a README from day one** with what it is, why it exists, how to run it, and a results table that starts empty. Update it every milestone.
- **CI** (GitHub Actions): lint, type-check and tests on every PR, plus the eval smoke test from milestone 3. Dependabot for both Python and npm.

### CLAUDE.md (rules for agents)
Put a short `CLAUDE.md` at the root so every agent session follows the project rules:
- Agents work in `api/`, `frontend/`, CI and Docker, through PRs you review.
- How to run the tests, the lint commands, and the commit style.

This also lets you show an interviewer how you used agents deliberately.

---

## 6. First week, in order

1. Create the repo, attach it here, and copy in the plan. *(You.)*
2. **Scaffold PR**: uv/pyproject, the folder layout, Makefile, pre-commit, CI, Dependabot, PR template, CLAUDE.md, `.env.example`. *(Claude can open this as a PR for you to review once the repo is attached.)*
3. Set up branch protection on `main` and require CI to pass. *(You, in GitHub settings.)*
4. Create Milestones 1–6 and the issues for Milestone 1. *(Claude can draft these.)*
5. Write ADR-001 on the morphology index design. *(You.)*
6. Start Milestone 1 yourself: a `data/scripts` downloader for the Wiktextract Latin dump, then the normaliser written test-first.

Done when: `make setup && make test && make lint` passes on a fresh clone, CI is green on `main`, and the first Milestone 1 issue is in progress.
