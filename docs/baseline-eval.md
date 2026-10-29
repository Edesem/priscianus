# Baseline eval: raw Claude on Latin parses

The M2 result ([#46](https://github.com/Edesem/priscianus/issues/46)). It measures what Claude does on its own, with no tools and no verifier, so that every later mode (M3 onwards) has a number to beat. The design is in [ADR-003](adr/ADR-003.md) and the set in [parse-set.md](parse-set.md).

**Headline.** On the 1,000-item test split, Claude gets between 79.6% (Haiku 5.5) and 86.8% (Opus 5.5) of Latin parses exactly right, and states a parse that the morphology index contradicts on 5.9% to 7.5% of items.

## Method

- **Set:** `parse-v1`, frozen. A stratified sample of tokens from the UD Latin treebanks (Perseus, PROIEL, ITTB; r2.18): 1,000 test items and 300 dev items, spread over Classical and Ecclesiastical Latin, five POS classes and three frequency bands. It overweights rare lemmas and verbs against running text, so these are not text-level accuracies.
- **Task:** the model sees the sentence and one target token, and returns the lemma, UPOS and morphological features as structured output.
- **Mode:** `raw`. No dictionary, no tool calls, no verifier.
- **Prompt:** `raw-parse-v3`, frozen before the run; the prompt ID is stored with every response, so runs on different prompts cannot be mixed.
- **Models:** `claude-haiku-5-5`, `claude-sonnet-5-5`, `claude-opus-5-5`, one run each per split, `--concurrency 8`.
- **Scoring:** exact match means lemma, UPOS and every gold feature agree with the gold. A claim is checked against the morphology index: *hallucination* is a claim the index contradicts, *unverifiable* is one it cannot judge (the form has no index entry, or the claim carries nothing to check).
- **Splits:** dev is the prompt-development split; test was run after the prompt was frozen. Dev and test are reported separately and never pooled.
- **Reproduce:**

```
make eval ARGS="run --mode raw --set parse --split test --model claude-sonnet-5-5 --max-cost 15"
make eval ARGS="report <run ids> --out docs/baseline-eval-test.md --sample 0"
```

The run commands read `ANTHROPIC_API_KEY` from the environment (`set -a; . ./.env; set +a` first). The full tables are in [baseline-eval-test.md](baseline-eval-test.md) and [baseline-eval-dev.md](baseline-eval-dev.md). They omit failure examples because those quote treebank sentences, which this repo does not redistribute.

## Numbers

| Split | Model | Exact match | Lemma | Hallucination | Unverifiable | Schema failures |
|---|---|---:|---:|---:|---:|---:|
| test | Haiku 5.5 | 79.6% | 90.4% | 7.5% | 14.3% | 0 |
| test | Sonnet 5.5 | 83.6% | 92.5% | 5.9% | 13.4% | 0 |
| test | Opus 5.5 | 86.8% | 92.8% | 5.9% | 13.0% | 0 |
| dev | Haiku 5.5 | 77.3% | 89.3% | 3.7% | 13.0% | 0 |
| dev | Sonnet 5.5 | 81.3% | 91.3% | 4.3% | 11.7% | 0 |
| dev | Opus 5.5 | 84.7% | 91.3% | 5.0% | 11.3% | 0 |

Dev is 300 items, so its rates move by about 2.5 points per 8 items; read dev as a sanity check, and test as the result. Dev's hallucination rates are lower than test's and do not preserve the model ordering; with 11 to 15 events each that is within noise.

"Index matches gold" is 79.3% on test: for 793 of 1,000 items the index contains the gold reading. All three models exceed that, so the index is a weaker oracle than the models and cannot be treated as the ground truth for scoring. That is also why "unverifiable" is large (see below).

### Cost and latency

| Model | Test cost | Per item | Dev cost | p50 / p95 latency (test) |
|---|---:|---:|---:|---|
| Haiku 5.5 | $0.17 | $0.00017 | $0.05 | 2.4 s / 4.4 s |
| Sonnet 5.5 | $1.65 | $0.00165 | $0.51 | 1.9 s / 2.9 s |
| Opus 5.5 | $3.75 | $0.0038 | $1.05 | 2.3 s / 4.2 s |

The whole baseline cost about $7.2 (test $5.58, dev $1.62). The prompt is about 1,950 input tokens per call (from the stored token counts); costs are as recorded by the run, including any caching.

## Where the models fail

All figures are test exact match unless stated. Order of the three models is Haiku / Sonnet / Opus.

- **Rare lemmas.** Exact match falls from 82.6 / 85.7 / 88.9% in the top-1k band to 70.5 / 74.0 / 79.8% in the rare band, and lemma accuracy to 81.5% for Haiku. Opus narrows the gap but does not close it. The lemma is often a near-miss in orthography: the model returns a normalised or classical spelling (`sequor` for the gold `secor`, `conicio` for `coicio`) where the treebank keeps the attested form.
- **Participles and passives.** Participles are the worst feature group: 38 / 43 / 50 of 67 exact, and 28 / 24 / 26 of them are contradicted by the index. The commonest mistake is leaving a feature out (gold `VerbForm=Part` answered with no VerbForm, Tense or Voice). Passive gold items: 63 / 67 / 76 of 90 exact, against 204 / 211 / 212 of 243 active.
- **Verbs and adjectives.** Verbs carry the highest hallucination rate (12.9% Haiku, 11.1% Opus) and adjectives and pronouns/determiners the lowest exact match for Haiku (69.3% each). Nouns are the strongest class (85.6 to 90.4%).
- **Case and gender.** The recurring feature confusions are Nom→Acc (15 for Haiku) and gender omitted or defaulted to masculine (`Masc`→none 18, `Fem`→`Masc` 9, `Neut`→`Masc` 9 for Haiku). Case accuracy is 94.3 / 97.7 / 98.7% and gender 91.2 / 93.2 / 94.9%.
- **Ambiguous forms.** When the index lists several readings for the form, exact match is 74.7% (Haiku), against 95.5% for single-reading forms. Most of the headroom is in choosing between valid readings from context, not in knowing the paradigm. Opus is at 86.8% on ambiguous forms.
- **Subjunctives.** Not a weakness here: gold subjunctive items are 33 / 34 / 33 of 37 exact. Imperatives are shakier for the two smaller models (5 / 4 / 9 of 9) but the sample is tiny.
- **Ecclesiastical spellings.** Contrary to what we expected, Ecclesiastical items score as well as or better than Classical for Haiku (81.4% vs 77.8%) and match for Sonnet and Opus (86.0% vs 87.6% for Opus). The rare Ecclesiastical band is the weaker part (Opus: 64 of 78 exact). I have not tested why Ecclesiastical text is no harder; the set does not isolate spelling variants.
- **Deponents.** Not measured separately: the set has no deponent stratum, so deponent errors are inside the voice figures above and cannot be separated. A dedicated slice is a candidate for `parse-v2`.
- **Schema.** No format failures in any of the 3,900 calls (3 models × 1,300 items), so structured output is not a failure source.

## Limits

- The sample is stratified and overweights rare lemmas and verbs; it says how the models do on hard cases, not on running Latin.
- One run per model and split. There is no estimate of run-to-run variance. Differences of a couple of points between Sonnet and Opus on a single feature are not reliable; the exact-match ordering Haiku < Sonnet < Opus is consistent on both splits.
- The gold is UD annotation, which is itself inconsistent across treebanks (the three treebanks follow different conventions). Some "errors" are annotation choices.
- Hallucination is measured against the morphology index, which is incomplete (see the 79.3% ceiling). A claim the index cannot confirm is counted as unverifiable, not wrong, so the hallucination rate is a lower bound.
- Uninflected items have almost no checkable claim (claim accuracy 2% for Haiku); their exact match is carried by lemma and UPOS.
- Haiku has a different dev history from the others: the 20-item smoke run was extended to the full split, so its dev run covers 280 fresh items plus 20 already stored.

## Hypotheses for M3

M3 adds tools (index lookup) and a verifier. Written before building them so they can be wrong.

**Should be fixed**

1. *Orthographic lemma drift* (`sequor` vs `secor`, `conicio` vs `coicio`) and rare-lemma errors: looking up the surface form in the index returns the attested lemma. Expect the rare band's lemma accuracy to rise most.
2. *Impossible parses*: the 5.9 to 7.5% of claims the index contradicts are exactly what a verifier can reject and retry. Target: hallucination rate below 2% on items whose form is in the index.
3. *Omitted features on participles*: a required-features check per VerbForm should catch the missing Tense/Voice/Gender answers.
4. *Model gap on ambiguous forms*: giving the model the full list of readings for the form should lift Haiku and Sonnet toward Opus on ambiguous items.

**Cannot be fixed by these tools**

1. *Choosing among valid readings from context*: the index lists candidates, it does not disambiguate. The remaining error on ambiguous forms is a reading problem and will need context-sensitive evidence or a stronger model.
2. *Forms the index lacks* (about 20% of gold readings are missing): the verifier will return "unverifiable" for these, and the tool-using model falls back to its own judgement. Growing the index is the only remedy; this is a data task.
3. *Annotation disagreement with UD*: a correct parse under another convention is still scored wrong.
4. *Unverifiable output is not an error*: 13 to 14% of test items are unverifiable, and uninflected words are most of them (97 of Haiku's 143, because there is no inflection to check). M3 should report them separately instead of folding them into a single accuracy.

**Primary M3 metrics:** exact match on the test split (baseline above), hallucination rate, and exact match on the ambiguous-form and rare-band slices.
