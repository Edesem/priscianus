# Spot-check against Whitaker's Words

Closes the validation step of M1 (issue #10): does the morphology index agree with Whitaker's Words on a spread of Latin forms?

## Method

- **Word list.** 144 forms covering declensions 1–5, adjectives (1st/2nd and 3rd declension, comparative and superlative), pronouns, the four regular conjugations plus 3rd-io, irregular verbs (*sum*, *possum*, *eo*, *fero*, *volo*), deponents, passives, infinitives, participles, gerunds and supines. The list is in `src/data/scripts/generate_whitakers_spot_check.py`.
- **Reference.** Whitaker's analyses were recorded with [PyWORDS](https://github.com/sjgallagher2/PyWORDS), a Python port of Whitaker's data and matching rules (MIT). The original Ada program was not available. PyWORDS does not use Whitaker's `ESSE` and `UNIQUES` files and drops some pronoun matches, so 14 forms got no analysis at all (*deo, eius, hic, illa, illi, sum, es, est, sunt, erat, fuit, fuerat, vult, locutus*). They are skipped, not counted as agreement, which leaves **130 forms compared**. The suppletive verbs and pronouns therefore still need checking by hand.
- **Fixture.** The recorded analyses are committed as `src/data/spot_check/whitakers.json`, keeping Whitaker's own codes, so the comparison runs without PyWORDS. Regenerate it with the script above in a throwaway virtualenv with PyWORDS installed.
- **Comparison.** `priscianus.morphology.whitakers` maps Whitaker's codes to UD features and checks, for each Whitaker's analysis of a form, that some index analysis of that form carries all of its features. Extra features in the index are not held against it. Run it with `python -m priscianus.morphology.whitakers` from `src/backend`.
- **Two expectations are relaxed**, because the index never records them: gender on noun forms (Wiktionary tables leave it to the lemma) and `Degree=Pos` on positive adjectives (Wiktionary does not tag it). Without this, about 20 further forms would show as disagreements for no useful reason.

## Result

**99 of 130 forms agree.** The 31 that do not fall into five causes. None is a tag-mapping bug: the mapping from Wiktionary tags and from Whitaker's codes produced the intended features everywhere it was exercised. Each disagreement is a gap or a convention difference in the data.

| Cause | Kind | Forms | Follow-up |
|---|---|---|---|
| Locative singular/plural listed for every noun and adjective in Whitaker's | Index gap (by design) | puellae, domini, pueri, regi, rege, nomine, mare, bonae, fortibus, amari, eris, ire | None. Wiktionary tabulates the locative only for place-like nouns. Nothing to fix unless the tutor needs it. |
| Participle, gerundive and supine split across two lemmas, so no analysis has both case and tense | Index gap (data model) | amatus, amantem, amandi, amatum, monitus, auditum, latum, exercitum | #29 |
| Comparative and superlative forms carry no `Degree` | Index gap | melior, meliorem, optimus, pulchriorem | #30 |
| Deponent passive-looking forms tagged `Voice=Act` by Wiktionary, `Pass` by Whitaker's | Convention difference (Wiktionary labelling) | loquitur, sequuntur, hortamur, moritur, utitur | #31 |
| Rare readings Whitaker's lists that Wiktionary lacks | Index gap | *rosarum* (participle of a rare verb), *esse* (participle of *edo*), *eris* (a noun), *ire* (2nd singular passive) | None individually |

A form can appear in more than one row; the counts above are of forms, not readings.

No disagreement was traced to a Wiktionary error. For *rosarum*, *esse* and *eris*, the Whitaker's reading is real but rare, and the index's missing reading is a gap, not a mistake.

## Follow-ups

- **A. [#29](https://github.com/Edesem/priscianus/issues/29)** Participles, gerundives and supines lack case and tense in one analysis.
- **B. [#30](https://github.com/Edesem/priscianus/issues/30)** Comparative and superlative forms have no Degree.
- **C. [#31](https://github.com/Edesem/priscianus/issues/31)** Decide voice for deponent verbs.

## Limits

- 130 forms is a spot-check, not coverage. It was chosen for spread across paradigms, not frequency.
- PyWORDS is a port, so a disagreement with it is not proof of a disagreement with the original program. The gaps above are all of kinds that are visible in the index itself (see the lookups in the follow-up issues), but the Whitaker's side was not cross-checked against the Ada binary.
- Agreement here means "the index has the analysis Whitaker's has". It does not test that the index lacks wrong analyses.
