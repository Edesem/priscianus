# Verified eval: raw vs tools vs verified Claude on Latin parses

The M3 result ([#78](https://github.com/Edesem/priscianus/issues/78)). It repeats the [M2 baseline](baseline-eval.md) with two more modes, so the three can be compared on the same items. The design is in [ADR-003](adr/ADR-003.md) and the set in [parse-set.md](parse-set.md).

**Headline.** Giving the model the morphology index as a tool lifts exact match by 2.8 points for Haiku and 3.3 for Sonnet on the 1,000-item test split. The verifier and repair loop on top add almost nothing (+0.4 and -0.1 points). Haiku with tools (82.4% to 82.8%) comes close to Sonnet raw (83.6%) at about a fifth of the cost, but does not clearly match it, and is slower. Sonnet with tools (86.9%) matches Opus raw (86.8%) at about 1.2 times the cost.

## Method

- **Set and splits:** `parse-v1`, frozen (1,000 test items, 300 dev items). Dev and test are reported separately and never pooled.
- **Modes:**
  - `raw`: no tools, no verifier (the M2 baseline, prompt `raw-parse-v3`).
  - `tools`: the model may look the form up in the morphology index (prompt `tools-parse-v1`).
  - `verified`: as `tools`, then each claim is checked against the index; a claim the index contradicts or cannot confirm is sent back with the index's readings for up to two repair attempts (prompt `verified-parse-v1`).
- **Models:** `claude-haiku-5-5` and `claude-sonnet-5-5` in all three modes. Opus 5.5 appears in `raw` only (from M2); I did not run it with tools, to save budget.
- **Frozen prompts:** the tools and verified prompts were run on dev first and not changed before the test runs.
- **Scoring:** exact match, hallucination and unverifiable are defined as in the baseline doc. The raw numbers are the stored M2 runs, not re-run. The index ceiling on test now reads 79.8% (798/1000); the baseline doc said 79.3%, so the index build has changed since M2. Raw hallucination rates are unchanged, but I did not re-score the raw runs under the new build.
- **Reproduce:**

```
make eval ARGS="run --mode tools --set parse --split test --model claude-sonnet-5-5 --concurrency 8 --max-cost 15"
make eval ARGS="run --mode verified --set parse --split test --model claude-sonnet-5-5 --concurrency 8 --max-cost 15"
make eval ARGS="report 2 3 11 12 13 14 --out ../../docs/verified-eval-test.md --sample 0"
make eval ARGS="report 1 5 7 8 9 10 --out ../../docs/verified-eval-dev.md --sample 0"
```

Run ids: test raw 2 to 4, tools 11 (Haiku) and 12 (Sonnet), verified 13 and 14; dev raw 1, 5, 6, tools 7 and 8, verified 9 and 10. Full tables: [verified-eval-test.md](verified-eval-test.md) and [verified-eval-dev.md](verified-eval-dev.md).

## Before and after

Test split, 1,000 items.

| Model | Mode | Exact match | Lemma | Hallucination | Unverifiable |
|---|---|---:|---:|---:|---:|
| Haiku 5.5 | raw | 79.6% | 90.4% | 7.5% | 14.3% |
| Haiku 5.5 | tools | 82.4% | 91.7% | 4.7% | 12.8% |
| Haiku 5.5 | verified | 82.8% | 91.8% | 4.3% | 12.7% |
| Sonnet 5.5 | raw | 83.6% | 92.5% | 5.9% | 13.4% |
| Sonnet 5.5 | tools | 86.9% | 93.3% | 4.8% | 12.3% |
| Sonnet 5.5 | verified | 86.8% | 93.5% | 4.6% | 12.3% |
| Opus 5.5 | raw | 86.8% | 92.8% | 5.9% | 13.0% |

Dev split, 300 items (a sanity check; one item is 0.33 points):

| Model | raw | tools | verified |
|---|---:|---:|---:|
| Haiku 5.5 | 77.3% | 82.7% | 82.7% |
| Sonnet 5.5 | 81.3% | 83.7% | 83.7% |
| Opus 5.5 | 84.7% | not run | not run |

One rate on 1,000 items has a 95% interval of about ±2.3 points, so differences under about 2 points between single runs are not reliable. Raw to tools is a 3-point move for both models on test and 2.4 to 5.4 on dev, which is consistent in direction but not large against that noise.

## Does Haiku + verifier match Sonnet or Opus raw?

| Setup | Exact (test) | Cost per item | Latency p50 / p95 |
|---|---:|---:|---|
| Haiku raw | 79.6% | $0.00017 | 2.4 s / 4.4 s |
| Haiku verified | 82.8% | $0.00034 | 3.8 s / 7.0 s |
| Sonnet raw | 83.6% | $0.00165 | 1.9 s / 2.9 s |
| Sonnet verified | 86.8% | $0.00478 | 3.5 s / 6.3 s |
| Opus raw | 86.8% | $0.00375 | 2.3 s / 4.2 s |

- **Haiku verified vs Sonnet raw:** 82.8% against 83.6%, a gap of 0.8 points, well inside the noise. So it is *nearly* level, not proven level. It costs about 20% as much per item ($0.00034 against $0.00165) and takes about twice as long.
- **Haiku verified vs Opus raw:** it does not match: 82.8% against 86.8%.
- **Sonnet verified vs Opus raw:** equal on exact match (86.8% each), at 1.3 times Opus's cost ($0.00478 against $0.00375) and 1.5 times its median latency. So there is no saving from this route; Opus raw is cheaper.
- **Answer to the plan's question:** with the index, a cheap model gets to about Sonnet-raw accuracy for about a fifth of the price. It does not reach Opus. The accuracy gain comes from the lookup tool, not from the verifier (next section).

### Cost and latency

These are per-item sums over all calls, using the cost and latency recorded when each call was first made. The `verified` runs replayed the tools runs' first-pass answers from the call cache, so the report's own "Cost" and "$ / item" columns for verified (and for dev tools Sonnet) show only the cache-miss spend and are far too low; the figures here use the stored first-call values instead. I did not fix the report; see the limits.

| Mode | Model | Test total | Per item | p50 / p95 | Tool calls per item |
|---|---|---:|---:|---|---:|
| raw | Haiku | $0.17 | $0.00017 | 2.4 s / 4.4 s | 0 |
| raw | Sonnet | $1.65 | $0.00165 | 1.9 s / 2.9 s | 0 |
| raw | Opus | $3.75 | $0.00375 | 2.3 s / 4.2 s | 0 |
| tools | Haiku | $0.32 | $0.00032 | 3.8 s / 6.1 s | 1.0 |
| tools | Sonnet | $4.43 | $0.00443 | 3.4 s / 5.3 s | 1.0 |
| verified | Haiku | $0.34 | $0.00034 | 3.8 s / 7.0 s | 1.0 |
| verified | Sonnet | $4.78 | $0.00478 | 3.5 s / 6.3 s | 1.0 |

Tools mode roughly doubles Haiku's cost and almost triples Sonnet's, because each answer needs a second model call and the lookup result adds input tokens. The verifier adds about 8% on top for Sonnet and 6% for Haiku, from the repair calls.

## Where verification helps

- **Tools, not repair, did the work.** Hallucination (claims the index contradicts) falls from 7.5% to 4.7% (Haiku) and 5.9% to 4.8% (Sonnet) as soon as the model can look the form up.
- **Rare lemmas.** Exact match in the rare band: Haiku 70.5% raw, 76.3% tools, 76.9% verified; Sonnet 74.0%, 79.8%, 79.8%. The gap to top-frequency items narrows but stays about 6 to 8 points.
- **Ambiguous forms.** Haiku on forms with several index readings: 74.7% raw, 81.7% verified. The model now sees every reading, so it picks among them better.
- **Adjectives and verbs.** Haiku adjectives 69.3% raw, 76.0% verified; Sonnet verbs 84.0% raw, 88.6% verified.
- **Feature omissions.** Haiku's tense accuracy goes from 94.9% to 97.1% and Sonnet's from 93.3% to 97.1%; both models stop leaving the feature out as often.

## Where it does not help or hurts

- **The repair loop is rare and nearly neutral.** On test, 47 Haiku items (4.7%) and 44 Sonnet items (4.4%) entered repair. Repair fixed 4 Haiku items and 0 Sonnet items, and made 0 and 1 items worse. Net effect: +0.4 and -0.1 points, which is noise. On dev, 3 and 7 items entered repair and none changed. The repair loop does not yet justify its extra calls; the evidence is that tools mode alone gives the gain.
- **Residual error stays high.** 15.4% (Haiku) and 11.6% (Sonnet) of verified final claims are still wrong. Of Haiku's 154, 134 were wrong items the index confirmed anyway ("false assurance"): the index lists several readings and the model chose a valid one that is not the gold one. The verifier cannot catch that.
- **Pronouns and determiners barely moved.** Haiku 69.3% raw, 70.0% verified.
- **Latency.** Verified mode is about 1.5 to 2 times slower than raw at the median, and its 95th percentile for Haiku is 7.0 s against 4.4 s.
- **Unverifiable items are unchanged** at 12 to 13%, mostly uninflected words and forms the index lacks. Verification cannot help these.

## Repair harm items, checked by hand

Test split: Haiku 0 items, Sonnet 1 item. Dev: none. I checked the one item.

*`perseus/phi0972.phi001.perseus-lat1.xml@774/3`, the form `stricto`, next to `gladio` in its sentence.*

- Gold: lemma `stringo`, ablative singular neuter perfect passive participle.
- Sonnet's first answer matched the gold exactly (neuter).
- The verifier did not confirm it, because the index lists this form's participle readings under the lemma `strictus`, not `stringo`, and its `strictus` entries carry no Aspect. The index therefore says the lemma exists but "not this reading".
- On repair Sonnet switched the gender to masculine, arguing that `stricto` agrees with `gladio`. That is correct Latin: `gladius` is masculine. I believe the gold annotation (neuter) is the mistake here, not Sonnet's repair. This is my own reading of the Latin and I did not check another source.

So this "harm" is two separate data problems, not a model failure: (1) an index problem, participles filed under the adjective lemma `strictus` instead of the verb lemma `stringo`, which makes the verifier reject correct answers and push the model to change them; and (2) a probable gold-annotation error. The first needs a fix to the index build.

One item is too few to say how common the index problem is. I did not search for other participles filed under an adjective lemma, so I do not know how many of the 134 "false assurance" or the disputed items share this cause.

## Limits

- One run per model, mode and split; no estimate of run-to-run variance.
- The sample overweights rare lemmas and verbs; the numbers describe hard cases, not running text.
- Opus was not run with tools or verified, so "Haiku/Sonnet + verifier vs Opus" compares only against Opus raw.
- The test runs of Haiku and Sonnet were interrupted by an exhausted API credit balance and resumed. Items already answered were kept; the resumed runs finished at 1,000 items with no format failures. I confirmed the item counts but did not diff the answers across the interruption.
- The report's cost and latency columns for `verified` runs are misleading because of cache replay (see above). The figures in this doc were recomputed from the stored per-call first-call values. A report fix should be a separate issue.
- Dev and test costs for tools Sonnet on dev ($0.049 reported) are also affected by the cache; use the list figures in `evals.db`.
- The gold is UD annotation and has errors of its own (see the harm item). The ceiling (index matches gold) is 79.8% on test, below every tools and verified score, so the index cannot be treated as ground truth.
- I did not measure the 2% hallucination target from the baseline hypotheses for forms that are in the index. The overall rate went from 5.9 to 7.5% down to 4.3 to 4.8%.
- This is the M3 result on a single set; it says nothing about the full tutoring app.
