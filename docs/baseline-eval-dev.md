# Eval report

The numbers are averages over a stratified sample that overweights rare lemmas and verbs compared with running text (ADR-003). Claim rates are over the items that gave a claim; exact match, lemma accuracy and the schema-failure rate are over all items; per-feature accuracy is over the answers whose gold marks the feature.

- Run 1: claude-haiku-5-5, raw mode, split dev, parse-v1, prompt raw-parse-v3, complete
- Run 5: claude-sonnet-5-5, raw mode, split dev, parse-v1, prompt raw-parse-v3, complete
- Run 6: claude-opus-5-5, raw mode, split dev, parse-v1, prompt raw-parse-v3, complete

## Headline

| Metric | #1 claude-haiku-5-5 dev | #5 claude-sonnet-5-5 dev | #6 claude-opus-5-5 dev |
|---|---:|---:|---:|
| Items | 300 | 300 | 300 |
| Parse exact match | 77.3% (232/300) | 81.3% (244/300) | 84.7% (254/300) |
| Index matches gold (ceiling) | 81.3% (244/300) | 81.3% (244/300) | 81.3% (244/300) |
| Lemma accuracy | 89.3% (268/300) | 91.3% (274/300) | 91.3% (274/300) |
| Claim accuracy | 83.3% (250/300) | 84.0% (252/300) | 83.7% (251/300) |
| Hallucination rate | 3.7% (11/300) | 4.3% (13/300) | 5.0% (15/300) |
| Unverifiable rate | 13.0% (39/300) | 11.7% (35/300) | 11.3% (34/300) |
| Schema-failure rate | 0.0% (0/300) | 0.0% (0/300) | 0.0% (0/300) |
| Cost | $0.0506 | $0.5114 | $1.0530 |
| Latency p50 / p95 | 2296 / 4059 ms | 1904 / 2581 ms | 2236 / 3710 ms |

## Accuracy by feature

| Feature | #1 claude-haiku-5-5 dev | #5 claude-sonnet-5-5 dev | #6 claude-opus-5-5 dev |
|---|---:|---:|---:|
| Aspect | 100.0% (29/29) | 96.6% (28/29) | 100.0% (29/29) |
| Case | 95.1% (173/182) | 96.2% (175/182) | 98.9% (180/182) |
| Degree | 100.0% (2/2) | 100.0% (2/2) | 100.0% (2/2) |
| Gender | 87.7% (150/171) | 88.9% (152/171) | 94.7% (162/171) |
| Mood | 97.5% (78/80) | 96.2% (77/80) | 96.2% (77/80) |
| Number | 98.5% (256/260) | 98.1% (255/260) | 98.5% (256/260) |
| Person | 100.0% (103/103) | 99.0% (102/103) | 100.0% (103/103) |
| Tense | 96.9% (94/97) | 92.8% (90/97) | 96.9% (94/97) |
| VerbForm | 97.1% (101/104) | 96.2% (100/104) | 97.1% (101/104) |
| Voice | 93.4% (85/91) | 93.4% (85/91) | 94.5% (86/91) |

## Run 1: claude-haiku-5-5 on dev

### By frequency band

| Frequency band | Items | Exact | Lemma | Claim acc. | Halluc. | Unverif. | Schema fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1k-10k | 93 | 79.6% (74/93) | 88.2% (82/93) | 88.2% (82/93) | 4.3% (4/93) | 7.5% (7/93) | 0.0% (0/93) |
| rare | 45 | 71.1% (32/45) | 86.7% (39/45) | 88.9% (40/45) | 6.7% (3/45) | 4.4% (2/45) | 0.0% (0/45) |
| top1k | 162 | 77.8% (126/162) | 90.7% (147/162) | 79.0% (128/162) | 2.5% (4/162) | 18.5% (30/162) | 0.0% (0/162) |

### By pos class

| POS class | Items | Exact | Lemma | Claim acc. | Halluc. | Unverif. | Schema fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| adj | 46 | 71.7% (33/46) | 89.1% (41/46) | 91.3% (42/46) | 2.2% (1/46) | 6.5% (3/46) | 0.0% (0/46) |
| noun | 76 | 86.8% (66/76) | 96.1% (73/76) | 96.1% (73/76) | 2.6% (2/76) | 1.3% (1/76) | 0.0% (0/76) |
| pron_det | 44 | 56.8% (25/44) | 86.4% (38/44) | 97.7% (43/44) | 2.3% (1/44) | 0.0% (0/44) | 0.0% (0/44) |
| uninflected | 30 | 86.7% (26/30) | 86.7% (26/30) | 3.3% (1/30) | 0.0% (0/30) | 96.7% (29/30) | 0.0% (0/30) |
| verb | 104 | 78.8% (82/104) | 86.5% (90/104) | 87.5% (91/104) | 6.7% (7/104) | 5.8% (6/104) | 0.0% (0/104) |

### By classical / ecclesiastical

| Classical / Ecclesiastical | Items | Exact | Lemma | Claim acc. | Halluc. | Unverif. | Schema fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| Classical | 150 | 78.7% (118/150) | 88.7% (133/150) | 81.3% (122/150) | 5.3% (8/150) | 13.3% (20/150) | 0.0% (0/150) |
| Ecclesiastical | 150 | 76.0% (114/150) | 90.0% (135/150) | 85.3% (128/150) | 2.0% (3/150) | 12.7% (19/150) | 0.0% (0/150) |

### Ambiguity handling

| Gold reading in the index | Exact match |
|---|---:|
| Ambiguous forms | 81.3% (126/155) |
| Single-reading forms | 88.6% (78/88) |

### Feature confusions

| Feature: gold → given | Items |
|---|---:|
| Gender: Masc → (none) | 10 |
| Case: Nom → Acc | 3 |
| Voice: Act → (none) | 3 |
| Gender: Fem → Masc | 2 |
| Gender: Fem,Masc → Neut | 2 |
| Gender: Neut → (none) | 2 |
| Gender: Neut → Masc | 2 |
| Number: Plur → Sing | 2 |
| Tense: Past → (none) | 2 |
| VerbForm: Part → (none) | 2 |
| Voice: Pass → (none) | 2 |
| Case: Abl → (none) | 1 |
| Case: Abl → Nom | 1 |
| Case: Acc → Abl | 1 |
| Case: Nom → Gen | 1 |
| Case: Nom → Voc | 1 |
| Case: Voc → Nom | 1 |
| Gender: Masc → Fem | 1 |
| Gender: Masc → Neut | 1 |
| Gender: Neut → Fem | 1 |
| Mood: Ind → Sub | 1 |
| Mood: Sub → Ind | 1 |
| Number: Sing → (none) | 1 |
| Number: Sing → Plur | 1 |
| Tense: Fut → Past | 1 |
| VerbForm: Gdv → Ger | 1 |
| Voice: Pass → Act | 1 |

### Failure examples

#### Format failure (0)


#### Hallucination (10)


#### Index disagreement (1)


#### Wrong reading (46)


#### Wrong and unverifiable (12)


## Run 5: claude-sonnet-5-5 on dev

### By frequency band

| Frequency band | Items | Exact | Lemma | Claim acc. | Halluc. | Unverif. | Schema fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1k-10k | 93 | 81.7% (76/93) | 89.2% (83/93) | 90.3% (84/93) | 3.2% (3/93) | 6.5% (6/93) | 0.0% (0/93) |
| rare | 45 | 73.3% (33/45) | 88.9% (40/45) | 82.2% (37/45) | 13.3% (6/45) | 4.4% (2/45) | 0.0% (0/45) |
| top1k | 162 | 83.3% (135/162) | 93.2% (151/162) | 80.9% (131/162) | 2.5% (4/162) | 16.7% (27/162) | 0.0% (0/162) |

### By pos class

| POS class | Items | Exact | Lemma | Claim acc. | Halluc. | Unverif. | Schema fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| adj | 46 | 76.1% (35/46) | 95.7% (44/46) | 87.0% (40/46) | 6.5% (3/46) | 6.5% (3/46) | 0.0% (0/46) |
| noun | 76 | 88.2% (67/76) | 93.4% (71/76) | 94.7% (72/76) | 3.9% (3/76) | 1.3% (1/76) | 0.0% (0/76) |
| pron_det | 44 | 63.6% (28/44) | 84.1% (37/44) | 95.5% (42/44) | 4.5% (2/44) | 0.0% (0/44) | 0.0% (0/44) |
| uninflected | 30 | 90.0% (27/30) | 90.0% (27/30) | 3.3% (1/30) | 0.0% (0/30) | 96.7% (29/30) | 0.0% (0/30) |
| verb | 104 | 83.7% (87/104) | 91.3% (95/104) | 93.3% (97/104) | 4.8% (5/104) | 1.9% (2/104) | 0.0% (0/104) |

### By classical / ecclesiastical

| Classical / Ecclesiastical | Items | Exact | Lemma | Claim acc. | Halluc. | Unverif. | Schema fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| Classical | 150 | 82.0% (123/150) | 90.7% (136/150) | 83.3% (125/150) | 5.3% (8/150) | 11.3% (17/150) | 0.0% (0/150) |
| Ecclesiastical | 150 | 80.7% (121/150) | 92.0% (138/150) | 84.7% (127/150) | 3.3% (5/150) | 12.0% (18/150) | 0.0% (0/150) |

### Ambiguity handling

| Gold reading in the index | Exact match |
|---|---:|
| Ambiguous forms | 81.9% (127/155) |
| Single-reading forms | 95.5% (84/88) |

### Feature confusions

| Feature: gold → given | Items |
|---|---:|
| Gender: Masc → (none) | 10 |
| Tense: Past → (none) | 4 |
| VerbForm: Part → (none) | 3 |
| Voice: Pass → (none) | 3 |
| Case: Nom → Acc | 2 |
| Case: Nom → Gen | 2 |
| Gender: Fem → Neut | 2 |
| Gender: Neut → Masc | 2 |
| Mood: Sub → Ind | 2 |
| Number: Plur → (none) | 2 |
| Number: Sing → Plur | 2 |
| Tense: Pres → (none) | 2 |
| Voice: Act → (none) | 2 |
| Aspect: Perf → (none) | 1 |
| Case: Acc → Nom | 1 |
| Case: Nom → Abl | 1 |
| Case: Voc → Nom | 1 |
| Gender: Fem → Masc | 1 |
| Gender: Fem,Masc → Neut | 1 |
| Gender: Masc → Fem | 1 |
| Gender: Masc → Neut | 1 |
| Gender: Neut → (none) | 1 |
| Mood: Ind → Imp | 1 |
| Number: Sing → (none) | 1 |
| Person: 1 → 2 | 1 |
| Tense: Past → Fut | 1 |
| VerbForm: Gdv → Ger | 1 |
| Voice: Pass → Act | 1 |

### Failure examples

#### Format failure (0)


#### Hallucination (11)


#### Index disagreement (2)


#### Wrong reading (40)


#### Wrong and unverifiable (5)


## Run 6: claude-opus-5-5 on dev

### By frequency band

| Frequency band | Items | Exact | Lemma | Claim acc. | Halluc. | Unverif. | Schema fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1k-10k | 93 | 84.9% (79/93) | 91.4% (85/93) | 91.4% (85/93) | 3.2% (3/93) | 5.4% (5/93) | 0.0% (0/93) |
| rare | 45 | 80.0% (36/45) | 86.7% (39/45) | 86.7% (39/45) | 8.9% (4/45) | 4.4% (2/45) | 0.0% (0/45) |
| top1k | 162 | 85.8% (139/162) | 92.6% (150/162) | 78.4% (127/162) | 4.9% (8/162) | 16.7% (27/162) | 0.0% (0/162) |

### By pos class

| POS class | Items | Exact | Lemma | Claim acc. | Halluc. | Unverif. | Schema fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| adj | 46 | 76.1% (35/46) | 91.3% (42/46) | 89.1% (41/46) | 2.2% (1/46) | 8.7% (4/46) | 0.0% (0/46) |
| noun | 76 | 89.5% (68/76) | 94.7% (72/76) | 96.1% (73/76) | 2.6% (2/76) | 1.3% (1/76) | 0.0% (0/76) |
| pron_det | 44 | 72.7% (32/44) | 81.8% (36/44) | 88.6% (39/44) | 11.4% (5/44) | 0.0% (0/44) | 0.0% (0/44) |
| uninflected | 30 | 90.0% (27/30) | 90.0% (27/30) | 3.3% (1/30) | 0.0% (0/30) | 96.7% (29/30) | 0.0% (0/30) |
| verb | 104 | 88.5% (92/104) | 93.3% (97/104) | 93.3% (97/104) | 6.7% (7/104) | 0.0% (0/104) | 0.0% (0/104) |

### By classical / ecclesiastical

| Classical / Ecclesiastical | Items | Exact | Lemma | Claim acc. | Halluc. | Unverif. | Schema fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| Classical | 150 | 86.0% (129/150) | 91.3% (137/150) | 82.7% (124/150) | 6.0% (9/150) | 11.3% (17/150) | 0.0% (0/150) |
| Ecclesiastical | 150 | 83.3% (125/150) | 91.3% (137/150) | 84.7% (127/150) | 4.0% (6/150) | 11.3% (17/150) | 0.0% (0/150) |

### Ambiguity handling

| Gold reading in the index | Exact match |
|---|---:|
| Ambiguous forms | 85.2% (132/155) |
| Single-reading forms | 96.6% (85/88) |

### Feature confusions

| Feature: gold → given | Items |
|---|---:|
| Gender: Masc → (none) | 3 |
| Voice: Act → (none) | 3 |
| Gender: Neut → Masc | 2 |
| Mood: Sub → Ind | 2 |
| Number: Plur → Sing | 2 |
| Tense: Past → (none) | 2 |
| VerbForm: Part → (none) | 2 |
| Voice: Pass → (none) | 2 |
| Case: Nom → Gen | 1 |
| Case: Nom → Voc | 1 |
| Gender: Fem → Neut | 1 |
| Gender: Fem,Masc → Neut | 1 |
| Gender: Masc → Fem | 1 |
| Gender: Neut → (none) | 1 |
| Mood: Ind → Imp | 1 |
| Number: Sing → (none) | 1 |
| Number: Sing → Plur | 1 |
| Tense: Past → Fut | 1 |
| VerbForm: Gdv → Ger | 1 |

### Failure examples

#### Format failure (0)


#### Hallucination (8)


#### Index disagreement (7)


#### Wrong reading (33)


#### Wrong and unverifiable (5)
