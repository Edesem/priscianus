# Priscianus — Project Plan

**One-line pitch:** an LLM tutor that explains Latin grammar and generates exercises, where every claim about a word form ("*amāvērunt* is 3rd person plural perfect active indicative of *amō*") is checked against an authoritative morphology source before the learner sees it. The project measures how often the raw model is wrong and how much verification fixes it.

**Scope:** Latin only (Classical and Ecclesiastical). Ancient Greek is out of scope.

---

## 0. Purpose, users and alternatives

### Core purpose
Chatbots are now the default way many people get help with Latin, and they are confidently wrong about word forms often enough to mislead a learner who can't yet tell. This tutor keeps what the LLM is good at (patient explanations, endless fresh exercises, answering "why?") and removes what it is bad at (inventing or misparsing forms) by checking every grammatical claim against real data.

### Who it's for
- **Self-taught adult learners** (Wheelock's, Lingua Latina, Duolingo graduates) with no teacher to catch mistakes.
- **High-school and university students** doing homework and exam revision on paradigms and parsing.
- **Readers of Ecclesiastical Latin** (Vulgate, liturgy, the Church Fathers): clergy, seminarians, choir and chant singers. This group is underserved by classical-focused tools, and it's a community you belong to.
- **Teachers**, as a stretch: generating verified worksheets.

### What they get
- Explanations they can trust, with a clear mark on anything verified, ambiguous or unknown.
- Unlimited drills targeted at their weak spots, with correct answer keys.
- Grading that is consistent and right, because the morphology engine grades and the LLM only writes the feedback.
- Help reading real texts, not just textbook sentences.

### Similar applications
| Tool | What it does | Gap this project fills |
|---|---|---|
| **Whitaker's Words**, **Collatinus**, **Perseus Word Study Tool** | Deterministic parsers: give every possible analysis of a form | Accurate but bare: no explanation, no context, no exercises, no tutoring. This project uses them as its ground truth. |
| **ChatGPT / Claude used directly** | Fluent explanations and exercises | No verification; errors on rare or ambiguous forms go unnoticed. This is what the eval measures. |
| **Duolingo Latin, Clozemaster, Legentibus** | Courses, vocabulary, graded reading | Fixed content, little grammar explanation on demand, no parsing help on texts you bring. |
| **New AI Latin apps** (e.g. Latinviva, Alia, "Latin Translator & Dictionary"/Latin Master) | AI conversation, translation, grammar notes | Marketed on AI features; none I found say how they check the model's grammar or publish accuracy numbers. *(Based on app-store listings only; not tested.)* |

I found no published benchmark of LLM accuracy on Latin morphology, so the eval itself would be a small original contribution.

### What you gain as the builder
- **The core AI-engineering skill:** deciding which parts the model should do and which parts code should do, and wiring them together with tool use, structured outputs and a verify-and-repair loop.
- **Evals done properly:** gold datasets, frozen test splits, hallucination metrics, model and mode comparisons, LLM-as-judge calibrated against your own scores. This is the part most junior portfolios skip and interviewers ask about.
- **Data engineering:** turning messy linguistic datasets (Wiktionary dumps, treebanks) into a clean, tested index, plus handling Unicode, normalisation and licensing.
- **Cost and latency trade-offs:** showing that a small model plus a verifier can match a big model, with numbers.
- **Python backend depth** alongside your React/TypeScript strength, so the project reads as full-stack AI.
- **A strong interview story:** "I measured how often Claude gets Latin wrong, found where it fails, and cut learner-facing errors from X% to Y%." You can only tell it because you know Latin yourself.
- **A real tool** for your own study and for your parish and chant community.

---

## 1. Scope for v1

| Decision | Default | Why |
|---|---|---|
| Language | **Latin only**, Classical and Ecclesiastical spelling | One language done well beats two done shallowly; Ecclesiastical Latin is a differentiator. |
| Platform | **Web app first** (React + TypeScript), React Native later | Easier to demo from a CV link; the API is reusable by your existing RN skills later. |
| Learner | Intermediate self-learner (knows the basics, wants drills and explanations) | That's you, so you can judge output quality yourself. |
| Verification scope | **Morphology only** (form ↔ lemma ↔ parse). Not syntax, not translation quality. | Morphology has a crisp right answer; syntax and translation are judged in the eval with a rubric, not a checker. |

**In v1**
- **Explain a form:** user pastes a word or a sentence; tutor parses each word and explains the grammar. Every parse is verified.
- **Generate drills:** "give me 10 perfect-tense verbs from the 3rd conjugation" or "decline *rēx* in the plural". Every expected answer is verified before the drill is shown.
- **Grade answers:** learner's answer is checked by the morphology engine, not the LLM. The LLM only writes the feedback.
- **Trust badges:** each claim in the UI is marked *verified*, *ambiguous (here are the other readings)*, or *unverifiable* (word not in the database).

**Not in v1:** full-text translation, audio, accounts and spaced repetition, mobile app.

---

## 2. Architecture

```
            ┌──────────── Web UI (React/TS) ────────────┐
            │ explain · drills · grading · trust badges │
            └───────────────────┬───────────────────────┘
                                │ REST/JSON
┌───────────────────────────────▼──────────────────────────────┐
│ API (Python, FastAPI)                                        │
│                                                              │
│  1. LLM step (Claude, tool use + structured output)          │
│     tools: lookup_form(word) · inflect(lemma, features)      │
│            · list_lemmas(filters)                            │
│     output: { text, claims: [{form, lemma, features}] }      │
│                                                              │
│  2. Verifier (deterministic, no LLM)                         │
│     for each claim → query morphology index                  │
│     → VERIFIED | AMBIGUOUS | CONTRADICTED | UNKNOWN          │
│                                                              │
│  3. Repair loop: CONTRADICTED claims are sent back to the    │
│     model with the DB's correct parses (max 2 retries),      │
│     then dropped or flagged if still wrong.                  │
└───────────────┬──────────────────────────────┬───────────────┘
                │                              │
     ┌──────────▼──────────┐        ┌──────────▼──────────┐
     │ Morphology index    │        │ Eval store          │
     │ SQLite: form, lemma,│        │ runs, claims,       │
     │ normalised features │        │ verdicts, costs     │
     └─────────────────────┘        └─────────────────────┘
```

Key design points:
- **Claims are structured, not parsed from prose.** The model must return each grammatical claim as JSON with a fixed feature schema (Universal Dependencies feature names: `Case`, `Number`, `Tense`, `Mood`, `Voice`, `Person`, `Gender`, `Degree`). Prose that contains an unstructured claim is a failure the eval counts.
- **Ambiguity is first-class.** Many forms have several valid parses (*amor*, *rēgī*, *-ae* endings). A claim is VERIFIED if it is one of the DB's parses; the UI shows the others.
- **Normalisation layer:** macrons, u/v and i/j, enclitics (*-que*, *-ne*, *-ve*) and Ecclesiastical spellings (*-ae* vs *-e*, *coelum*/*caelum*) are handled in one tested module. This is where many bugs will live, so it gets its own unit tests.
- **Three modes for the comparison:** `raw` (no tools, no verifier), `tools` (model can call lookups), `verified` (tools + verifier + repair). The eval runs all three.

---

## 3. Data sources and licences

| Source | Use | Licence (check before publishing) |
|---|---|---|
| **Wiktionary inflection tables via Wiktextract / kaikki.org** | Main form→lemma→features index (full paradigms, macrons) | CC BY-SA 4.0 (+ GFDL). Attribute and share derived DB alike. |
| **Perseus Latin Dependency Treebank (part of AGLDT)** | Gold eval data: real words in real sentences with hand-checked morphology | CC BY-SA 3.0 |
| **Universal Dependencies Latin** (Perseus, PROIEL, ITTB, LLCT, UDante) | Extra gold eval data; PROIEL includes the Vulgate, useful for Ecclesiastical Latin | Mostly **CC BY-NC-SA**: fine for a non-commercial portfolio project, note it in the README. |
| **Whitaker's Words** | Fallback analyser for forms Wiktionary lacks | Freely distributable; confirm terms in the source. |
| **Collatinus** | Second-opinion lemmatiser, gives vowel quantities | Open source; confirm licence before bundling data. |
| **Morpheus** (Perseus analyser, Perseids fork) | Optional third opinion | Verify the repo's licence; if unclear, call it as a separate service rather than redistributing data. |
| **Perseus canonical-latinLit texts**, Vulgate | Sentences for drills and "explain this line" demos | CC BY-SA 4.0 (Perseus); Vulgate text is public domain. |

Default: **Wiktextract for the index, Perseus treebank + UD for evals.** Using independent sources means the eval isn't just grading the index against itself. Keep a `DATA_LICENCES.md` in the repo; recruiters notice this.

---

## 4. Eval design

The eval is the headline of the project. Put the results table at the top of the README.

### Datasets
1. **Parse set (gold):** ~1,000 tokens sampled from the Perseus/UD Latin test splits, stratified by part of speech and frequency band (top 1k lemmas, 1k–10k, rare), with a Classical and an Ecclesiastical slice. Task: "parse this word in this sentence".
2. **Generation set:** ~200 drill prompts ("give the 2nd person plural future passive of *capiō*", "list 5 neuter 3rd-declension nouns"). Gold answers come from the index.
3. **Explanation set:** ~50 sentences you pick (Caesar, Vulgate, liturgical Latin) for prose explanations. Scored with a rubric by you, plus an LLM judge.
4. **Adversarial set:** ~100 traps: ambiguous forms, deponents, irregular verbs (*ferō*, *eō*), defective nouns, invented non-words ("parse *amabavit*"). The correct behaviour for a non-word is to say so.

### Metrics
| Metric | Definition |
|---|---|
| **Claim accuracy** | VERIFIED claims ÷ all claims |
| **Hallucination rate** | CONTRADICTED claims ÷ all claims (the model said something the DB says is false) |
| **Unverifiable rate** | UNKNOWN claims ÷ all claims (tracks coverage gaps in the index, not model error) |
| **Parse exact match** | Full feature bundle matches the treebank gold for that token in context |
| **Ambiguity handling** | On ambiguous forms: did it pick the reading that fits the context (vs. gold) and mention alternatives? |
| **Non-word refusal** | Share of invented forms correctly rejected |
| **Residual error after repair** | Errors that survive the verified pipeline and reach the learner (the number that matters for users) |
| **Cost and latency** | Tokens, $ and p50/p95 latency per request, per mode |

### Comparisons
- `raw` vs `tools` vs `verified`, and at least two model sizes (e.g. Claude Haiku 5.5 vs Sonnet 5.5). The expected story: small model + verifier ≈ big model raw, at a fraction of the cost.
- Break every metric down by frequency band, part of speech and Classical vs Ecclesiastical. The interesting finding is *where* the model fails (rare lemmas, subjunctives, deponents, Ecclesiastical spellings), not the average.
- **LLM-as-judge calibration:** you hand-score the explanation set, then measure agreement (Cohen's κ) between you and the judge. Report it honestly, even if it's low.

### Mechanics
- Evals are a CLI (`python -m evals run --mode verified --set parse`) writing results to SQLite plus a markdown report.
- A small smoke eval (~50 items) runs in **GitHub Actions** on every PR and fails the build if hallucination rate regresses past a threshold. The full suite runs nightly or by hand. This uses the CI experience you already have.
- Freeze the test splits; tune prompts only on a separate dev split, and say so in the README.

---

## 5. Milestones

Each one ends with something you can demo.

1. **Morphology index** — Load Wiktextract Latin into SQLite, write the normaliser and `lookup_form` / `inflect` with unit tests (pytest). Spot-check against Whitaker's Words. *Demo: CLI that parses any Latin word.*
2. **Baseline eval first** — Build the parse set from the Perseus/UD treebanks and run the `raw` model on it. *Demo: "Claude gets X% of Latin parses exactly right, and hallucinates on Y%."* Doing this before building the tutor gives you the problem statement.
3. **Verified pipeline** — Structured claims, tools, verifier, repair loop. Run all three modes. *Demo: the before/after table.*
4. **Tutor web app** — Explain, drills and grading screens with trust badges; deploy (Fly.io or Render for the API, Vercel or Netlify for the front end). Add the CI smoke eval. *Demo: public URL.*
5. **Context and Ecclesiastical Latin** — Use the sentence to choose between ambiguous parses, add Ecclesiastical spelling support and a Vulgate/liturgical text mode, and report Classical vs Ecclesiastical error rates. *Demo: "explain this line of the Mass" with every form verified.*
6. **Write-up** — README with results, a short blog post on the failure analysis, a 2-minute demo video. Optional: expose the morphology index as an **MCP server** so any agent can use it (the "quick side project" from the idea list, reusing work you've already done).

Stretch: React Native client, spaced repetition on missed forms, teacher worksheet export.

---

## 6. Tech stack

| Layer | Choice | Note |
|---|---|---|
| LLM | Anthropic Claude API: Haiku 5.5 for drills and grading feedback, Sonnet 5.5 for sentence explanations; Sonnet 5.5 as the eval judge | Tool use + structured JSON output; prompt caching for the system prompt and tool definitions. See section 8 for costs. |
| Backend | Python 3.12, FastAPI, Pydantic | Python has the NLP ecosystem (treebank readers, `conllu`), and you already know Python and Django. |
| Data | SQLite (index + eval results) | Small, fast, portable, and you used it in BibleSearch. |
| Data prep | Python scripts, `conllu`, `unicodedata` | Reproducible `make data` step; don't commit the large raw dumps. |
| Front end | React + TypeScript + Vite | Your strongest area; a clean UI makes the demo land. |
| Tests | pytest (backend), Vitest + React Testing Library (front end) | |
| CI | GitHub Actions: lint (ruff, eslint), type-check (mypy, tsc), tests, smoke eval | Dependabot, as in your other repos. |
| Observability | Log every LLM call (prompt, claims, verdicts, tokens) to SQLite | Gives you the failure examples for the write-up. |

---

## 7. Risks

- **Index coverage gaps** look like model errors. Track the unverifiable rate separately and fill gaps from a second source.
- **Macrons and orthography** differ across sources (Wiktionary has macrons, treebanks mostly don't) and between Classical and Ecclesiastical spelling. Compare on a normalised key, and test the normaliser heavily.
- **Feature-schema mismatches** between Wiktionary tags, Perseus tags and UD features. Write one mapping module to UD features early, in milestone 1.
- **Eval overfitting:** keep test splits frozen and report dev and test numbers separately.
- **API cost:** the full eval in three modes × two models is a few thousand calls; cache responses keyed by prompt hash so re-running reports is free.

---

## 8. Models, costs and monetisation

### Models (Anthropic API prices per million tokens, input / output, as of Oct 2026)
| Model | Price | Use here |
|---|---|---|
| Claude Haiku 5.5 (`claude-haiku-5-5`) | $0.10 / $0.50 | Default for drills, grading feedback, single-word parses. The verifier catches its mistakes, so a cheap model is viable. |
| Claude Sonnet 5.5 (`claude-sonnet-5-5`) | $2 / $10 (cached input $0.20) | Sentence explanations and the LLM judge in evals. |
| Claude Opus 5.5 (`claude-opus-5-5`) | $4 / $20 | Eval comparison only ("does a bigger model help?"); not needed in the product. |

### Estimated cost per request
Assumes ~3k tokens of cached system prompt and tools, ~2k fresh input, ~1.5k output (including thinking), two tool round trips. These are estimates; measure real numbers from the call log in milestone 3.
- Haiku 5.5: about **$0.001** per request.
- Sonnet 5.5: about **$0.02** per request.
- An 80/20 Haiku/Sonnet mix averages about **$0.005** per request, so a heavy user doing 300 requests a month costs about **$1.50**.

### Development and hosting
- Full eval (1,000 parse items × 3 modes × 2 models plus the smaller sets): roughly **$50–100 per full run** at standard prices, about half that with the Batch API. Cache responses so re-running reports is free; the CI smoke eval costs cents.
- Hosting: free tiers or about **$5–10 a month** (Fly.io/Render for the API, Vercel/Netlify for the front end; SQLite needs no database server).
- Set a monthly spend limit on the Anthropic account from day one.

### Monetisation: free with limits first, subscription later
- **Launch free** with a daily limit on AI requests (default: 20 a day per user), enforced server-side. Deterministic features (form lookup, paradigm tables) are unlimited because they cost nothing.
- **Add a subscription only if people use it** (for example A$5 a month for higher limits and saved progress). Payments mean accounts, Stripe, refunds and support, which slows the part that matters for the CV: the eval and real users. Selling inside an iOS/Android app also means App Store / Play in-app billing and their cut.
- Even without charging, rate limiting, per-user quotas and cost tracking are worth building and talking about in interviews.

---

## Sources (similar apps)
- [Clozemaster: Best Apps to Learn Latin 2026](https://www.clozemaster.com/blog/?p=7283)
- [Latin Translator & Dictionary / Latin Master (App Store)](https://apps.apple.com/us/app/-/id6459021825)
- [Latinviva and similar apps (AppsHunter)](https://appshunter.io/ios/app/latinum-keyboard/id6758877995/similar)
- [Whitaker's Words (Debian package)](https://packages.debian.org/sid/whitakers-words)
- [LiLa workshop slides on Latin tools incl. Collatinus](https://lila-erc.eu/wp-content/uploads/2019/03/verkerk-lila-ws.pdf)
