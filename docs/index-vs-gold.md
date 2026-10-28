# Index agreement with the treebank gold

Before any model runs: how often does the morphology index itself agree with the gold parses of [parse-v1](parse-set.md)? Without this, an index gap or a convention difference would be counted as a model hallucination. Closes #40.

## Method

- **Items.** All 1,300 parse-v1 items (test 1,000, dev 300). Nothing is tuned on them.
- **Three nested checks** per item (`evals.index_agreement.check_token`): the surface form is in the index; the gold lemma (same `key_loose`, treebank lemma quirks removed) is among the lemmas of its analyses; some analysis `match()`es the gold parse, with the canonicalisation and relaxations of [ADR-003](adr/ADR-003.md), Decision 2.
- **Run it** with `cd src/evals && uv run python -m evals index-agreement --sample 120 --sample-out disagreements.json`.
- **Sample.** 120 of the 322 disagreements, drawn with seed 40, classified as in [whitakers-spot-check.md](whitakers-spot-check.md).

## Result

**The index has a matching analysis for 75.2% of the 1,300 items.** Uninflected words (adverbs, prepositions, conjunctions, particles) are not in the index by design and ADR-003 scores them on class and lemma only, so the ceiling for the items the index is meant to cover is **83.6% of the 1,170 inflected items**. These are the ceilings to quote next to the baseline numbers; a model cannot be expected to agree with the index more often than the index agrees with the gold.

## Treebank

| Group | Items | Form in index | Gold lemma found | Parse matches |
|---|---|---|---|---|
| ittb | 326 | 87.4% | 77.3% | 76.7% |
| perseus | 418 | 89.0% | 79.4% | 77.3% |
| proiel | 556 | 88.8% | 79.5% | 72.8% |

## POS class

| Group | Items | Form in index | Gold lemma found | Parse matches |
|---|---|---|---|---|
| adj | 196 | 94.9% | 85.7% | 83.7% |
| noun | 326 | 98.8% | 96.9% | 96.3% |
| pron_det | 194 | 100.0% | 98.5% | 87.1% |
| uninflected | 130 | 13.8% | 0.0% | 0.0% |
| verb | 454 | 94.9% | 77.3% | 72.9% |

## Frequency band

| Group | Items | Form in index | Gold lemma found | Parse matches |
|---|---|---|---|---|
| 1k-10k | 381 | 97.1% | 83.2% | 81.1% |
| rare | 218 | 85.3% | 72.9% | 68.3% |
| top1k | 701 | 84.9% | 78.5% | 74.2% |

## Classical / Ecclesiastical

| Group | Items | Form in index | Gold lemma found | Parse matches |
|---|---|---|---|---|
| Classical | 650 | 88.6% | 78.9% | 75.1% |
| Ecclesiastical | 650 | 88.5% | 78.9% | 75.4% |


Nouns agree almost always. Verbs lose the most (gold lemma found for only 77%), and PROIEL agrees less than the other two treebanks (72.8% against 76.7% and 77.3%). Classical and Ecclesiastical items agree about equally.

## Disagreements

Classification of the 120 sampled disagreements. A line counts under the first cause that fits. No Wiktionary error was found in the sample.

| Cause | Kind | Sampled | Follow-up |
|---|---|---|---|
| Uninflected words are not in the index | Index gap (by design) | 44 | None; scored on class and lemma only (ADR-003) |
| Gold lemma of a participle, gerund, gerundive or supine is the verb (*paventes* → *paveo*); the index lemma is the participle (*pauens*) | Gold convention difference | 31 | Follow-up issue to open: link participles to their verb |
| Gold lemma of a comparative or superlative is the positive (*maiores* → *magnus*); the index lemma is *maior* | Gold convention difference | 5 | Same issue |
| Personal pronouns: gold gives Gender=Masc to *ego*, *tu*, *nos*, *vos*, and Number to *se*; the index marks neither | Gold convention difference | 12 | Recorded in ADR-003; not relaxed |
| Lemma spelt differently (*adfirmo*/*affirmo*, *intellego*/*intelligo*, *inmundus*/*immundus*) or lemmatised differently (*dolui* → *deoleo*) | Gold convention difference | 10 | Recorded in ADR-003 |
| Form or lemma not in the index (*praeaccipit*, *nuntiarint*, *complacentiam*, *ringentem*, *custodistis*, *Clodiana*) | Index gap | 16 | Follow-up issue to open: syncopated perfects and rare lemmas |
| Form in the index without the gold reading (*hydraule* ablative, *Ortygiam* as an adjective) | Index gap | 2 | None individually |

**Mapping bug, fixed.** An earlier run of the same sample showed 16 pronouns failing only on `Person`: the gold marks it (*ego* 1, *tu* 2, *is* 3) and index pronoun forms never carry it. Person on a pronoun belongs to the lemma, as gender does on a noun, so `matches()` no longer compares it (ADR-003 relaxation table). That moved the ceiling from 71.7% to 75.2%.

## Limits

- 120 of 322 disagreements were classified, by cause rules read against the individual forms, so the counts are proportions of a sample: read them as roughly, not exactly.
- Agreement means the index has the analysis the gold has. It does not show that the index lacks wrong analyses.
- The 75.2% rests on the relaxations already in ADR-003, plus person on pronouns. Linking participle and degree lemmas would resolve about 30% of the disagreements in the sample (36 of 120).
