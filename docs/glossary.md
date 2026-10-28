# Glossary

Terms used in the Priscianus docs, grouped by area. Where a term is decided in an ADR, the ADR is linked.

## Eval

| Term | Meaning |
|---|---|
| **Eval** | A repeatable test. It runs the model on a fixed set of items and scores the answers against gold answers. |
| **Raw model** | The language model on its own, with no tools and no verifier. It is the control that the other modes are compared against. |
| **Tools mode** | The model may call the index lookups (`lookup_form`, `inflect`, `list_lemmas`), but nothing checks its final claims. |
| **Verified mode** | Tools, plus the verifier and the repair loop. |
| **Parse** | Working out a word's lemma, part of speech and features from its sentence. |
| **Parse set** | About 1,000 test words, each with its sentence and gold answer. The baseline eval runs on it ([ADR-003](adr/ADR-003.md)). |
| **Gold source** | The hand-checked treebanks that the model's answers are scored against. ADR-003 uses the UD Latin treebanks, release r2.18. It is kept separate from the index so that index errors are not counted as correct model output. |
| **Gold answer** | The correct analysis of one word in its sentence, taken from the gold source. |
| **Split** | A fixed part of the data. **Dev** is for tuning prompts. **Test** is for the numbers reported. |
| **Manifest** | The committed list of item IDs and hashes that defines the parse set. It holds no treebank text. |
| **Seed** | The number that fixes the random sample, so the same inputs always give the same set. |
| **Frozen** | A published set version never changes. A change gets a new version name, such as `parse-v2`. |
| **Smoke eval** | A small subset (about 50 items) run in CI on every pull request. It fails the build if the hallucination rate gets worse. |
| **Response cache** | Stored API responses, keyed by a hash of the request. Re-running a report costs nothing. |
| **Residual error** | An error that survives the verified pipeline and still reaches the learner. |

## Treebanks and Universal Dependencies

| Term | Meaning |
|---|---|
| **Treebank** | A collection of sentences in which every word has been annotated by hand: its lemma, part of speech, features and syntactic head. The name comes from the dependency trees the annotation forms. |
| **Universal Dependencies (UD)** | A shared annotation standard used across many languages. Every treebank in this project uses it. |
| **UD release** | A numbered version of the UD treebanks. The project pins **r2.18**, so the data does not change under the eval. |
| **CoNLL-U** | The plain-text format that UD treebanks come in. One word per line, ten tab-separated columns, and a blank line between sentences. |
| **`sent_id`** | The unique ID of a sentence within a treebank. The manifest refers to items by sentence ID and word ID. |
| **Word ID** | The position of a word within its sentence, as in the first column of CoNLL-U. |
| **Multiword token** | One written form split into two words, such as *virumque* → *virum* + *-que*. Words inside one are excluded from the parse set, because the model would have no single surface form to parse. |
| **Test split / train split** | The test split is a treebank's held-out sentences, used for evaluation. The train split is used for training. Here it is used to count how often each lemma occurs. |
| **Perseus, PROIEL, ITTB** | The three UD Latin treebanks in the parse set. Perseus covers Classical texts, PROIEL covers the Vulgate and some Cicero and Caesar, and ITTB covers Thomas Aquinas. All three are CC BY-NC-SA. |

## Morphology

| Term | Meaning |
|---|---|
| **Form** | A word as written, such as *amātus*. |
| **Lemma** | The dictionary form of a word. For example, *loquitur* has the lemma *loquor*. |
| **Part of speech (UPOS)** | The coarse word class, such as `VERB`, `NOUN`, `ADJ` or `PRON`. |
| **UD features** | Grammatical properties written in the FEATS column, such as `Case=Abl|Number=Plur`. |
| **Case, Number, Gender, Person** | Nominal and verbal agreement features. Values include `Nom`/`Gen`/`Dat`/`Acc`/`Abl`/`Voc` for case and `Sing`/`Plur` for number. |
| **Tense, Aspect** | `Tense` covers `Pres`, `Past`, `Fut` and `Pqp`. `Aspect` is `Imp` or `Perf`. UD writes the imperfect and perfect as `Tense=Past` with different `Aspect` values, and the future perfect as `Tense=Fut|Aspect=Perf`. |
| **Mood, VerbForm** | `Mood` is `Ind`, `Sub` or `Imp`. `VerbForm` is `Fin` (finite), `Inf` (infinitive), `Part` (participle), `Ger` (gerund), `Gdv` (gerundive) or `Sup` (supine). |
| **Voice** | `Act` or `Pass`. Deponent verbs are passive in form but active in meaning, so their voice is not compared ([ADR-002](adr/ADR-002.md)). |
| **Degree** | `Pos`, `Cmp` (comparative) or `Sup` (superlative). |
| **Deponent** | A verb that has passive forms but an active meaning, such as *loquor*. |
| **Participle** | A verb form used as an adjective or noun, such as *amatus*. UD lists it under the verb's lemma, while Wiktionary often gives it its own entry ([#29](https://github.com/Edesem/priscianus/issues/29)). |
| **Enclitic** | A suffix attached to a word, such as *-que*, *-ne* or *-ve*. The index handles enclitics in the query layer, not in the data. |
| **Canonical form** | The one agreed form of a set of features after the treebanks' differences are resolved. For example, `Degree=Pos` is dropped, and `Aspect` is kept only with the past tenses. The eval and the verifier both use it ([ADR-003](adr/ADR-003.md), Decision 2). |

## Index and verifier

| Term | Meaning |
|---|---|
| **Morphology index** | The project's read-only SQLite database of forms, lemmas and analyses. It is built from Wiktionary by `make data` ([ADR-001](adr/ADR-001.md)). |
| **Wiktionary** | The collaborative dictionary whose inflection tables the index is built from. It is licensed CC BY-SA 4.0. |
| **Wiktextract / kaikki.org** | A tool, and the site that distributes its output, which turns Wiktionary into structured JSON. The index reads the kaikki.org Latin dump. |
| **Analysis** | One reading of a form: its lemma, part of speech and features. |
| **Reading** | One distinct analysis of a form after normalisation. Two index rows that agree on lemma and features are one reading. |
| **Claim** | A statement the model makes about a word: its form, lemma, part of speech and features. |
| **Verifier** | Deterministic code, with no LLM, that checks each claim against the index and gives it a verdict. |
| **Verdict** | The verifier's label for a claim. See the verdicts table below. |
| **Normaliser** | The code that maps spellings to comparable keys. It handles macrons, u/v and i/j. |
| **`key_loose`** | The normalised key with macrons removed. Used for lookups of treebank and user input. |
| **`key_macron`** | The normalised key that keeps vowel length. Used when a claim includes macrons. |
| **Frequency band** | Whether a lemma is in the top 1,000, in the 1,001–10,000 range, or rare. The bands are counted from UD train splits and used to sample the parse set. |
| **Lemma coverage** | Whether the index has the claimed lemma at all. It decides between CONTRADICTED and UNKNOWN. |

### Verdicts

| Verdict | Meaning |
|---|---|
| **VERIFIED** | The claim matches a reading, and the form has no other reading. |
| **AMBIGUOUS** | The claim matches a reading, but the form has other readings too. The claim is not wrong. |
| **CONTRADICTED** | The claimed lemma is in the index, but no reading of the form matches the claim. This is a hallucination. |
| **UNKNOWN** | The claimed lemma is not in the index, so the index cannot say whether the claim is true. |

## Metrics

| Term | Meaning |
|---|---|
| **Exact match** | The share of items where the model's part of speech and every gold-marked feature equal the gold answer. |
| **Per-feature accuracy** | For each feature, the share of items where the gold marks that feature and the model gets its value right. |
| **Lemma accuracy** | The share of items where the model's lemma matches the gold lemma. |
| **Claim accuracy** | (VERIFIED + AMBIGUOUS) ÷ all claims. A right reading of an ambiguous form counts as right. |
| **Hallucination rate** | CONTRADICTED ÷ all claims. |
| **Unverifiable rate** | UNKNOWN ÷ all claims. It measures gaps in the index, not model errors. |
| **Format failure rate** | The share of items with no valid JSON answer. |
| **Index disagreement** | An item where the model matches the gold answer, but the verifier marks its claim CONTRADICTED. It points to an index error, which is fixed in the index build, not in the eval. |

## Pipeline

| Term | Meaning |
|---|---|
| **Repair loop** | In verified mode, CONTRADICTED claims are sent back to the model with the correct parses. This runs at most twice. Claims still wrong after that are dropped or flagged. |
| **ADR** | Architecture decision record. A short document in `docs/adr/` that records one decision, its options and its consequences. |

## Licences

| Term | Meaning |
|---|---|
| **CC BY-SA 4.0** | Creative Commons Attribution-ShareAlike. Derived works must credit the source and carry the same licence. The built index is a derived work of Wiktionary. |
| **CC BY-NC-SA** | The same, plus a non-commercial restriction. Perseus, PROIEL and ITTB in UD are under it. Their text is never committed. |
| **Derived database** | `morphology.db`, built from Wiktionary. Any published copy must be CC BY-SA 4.0. |
