# Eval report

The numbers are averages over a stratified sample that overweights rare lemmas and verbs compared with running text (ADR-003). Claim rates are over the items that gave a claim; exact match, lemma accuracy and the schema-failure rate are over all items; per-feature accuracy is over the answers whose gold marks the feature.

- Run 1: claude-haiku-5-5, raw mode, split dev, parse-v1, prompt raw-parse-v3, complete
- Run 5: claude-sonnet-5-5, raw mode, split dev, parse-v1, prompt raw-parse-v3, complete
- Run 7: claude-haiku-5-5, tools mode, split dev, parse-v1, prompt tools-parse-v1, complete
- Run 8: claude-sonnet-5-5, tools mode, split dev, parse-v1, prompt tools-parse-v1, complete
- Run 9: claude-haiku-5-5, verified mode, split dev, parse-v1, prompt verified-parse-v1, complete
- Run 10: claude-sonnet-5-5, verified mode, split dev, parse-v1, prompt verified-parse-v1, complete

## Headline

| Metric | #1 claude-haiku-5-5 dev | #5 claude-sonnet-5-5 dev | #7 claude-haiku-5-5 dev | #8 claude-sonnet-5-5 dev | #9 claude-haiku-5-5 dev | #10 claude-sonnet-5-5 dev |
|---|---:|---:|---:|---:|---:|---:|
| Items | 300 | 300 | 300 | 300 | 300 | 300 |
| Parse exact match | 77.3% (232/300) | 81.3% (244/300) | 82.7% (248/300) | 83.7% (251/300) | 82.7% (248/300) | 83.7% (251/300) |
| Index matches gold (ceiling) | 82.0% (246/300) | 82.0% (246/300) | 82.0% (246/300) | 82.0% (246/300) | 82.0% (246/300) | 82.0% (246/300) |
| Lemma accuracy | 89.3% (268/300) | 91.3% (274/300) | 92.0% (276/300) | 92.0% (276/300) | 92.0% (276/300) | 92.3% (277/300) |
| Claim accuracy | 83.3% (250/300) | 84.0% (252/300) | 88.0% (264/300) | 86.7% (260/300) | 88.0% (264/300) | 87.0% (261/300) |
| Hallucination rate | 3.7% (11/300) | 4.3% (13/300) | 1.0% (3/300) | 2.0% (6/300) | 1.0% (3/300) | 1.7% (5/300) |
| Unverifiable rate | 13.0% (39/300) | 11.7% (35/300) | 11.0% (33/300) | 11.3% (34/300) | 11.0% (33/300) | 11.3% (34/300) |
| Schema-failure rate | 0.0% (0/300) | 0.0% (0/300) | 0.0% (0/300) | 0.0% (0/300) | 0.0% (0/300) | 0.0% (0/300) |
| Cost | $0.0506 | $0.5114 | $0.0930 | $0.0489 | $0.0021 | $1.3167 |
| Latency p50 / p95 | 2296 / 4059 ms | 1904 / 2581 ms | 3924 / 5931 ms | 4363 / 5087 ms | 7470 / 7703 ms | 3675 / 5234 ms |

## Modes compared

| Mode | Model | Exact | Lemma | Halluc. | Unverif. | Residual error | Repair success / harm | Tool calls / item | $ / item | Latency p50 / p95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| raw | claude-haiku-5-5 | 77.3% (232/300) | 89.3% (268/300) | 3.7% (11/300) | 13.0% (39/300) | 19.3% (58/300) | – | 0.0 | $0.0002 | 2296 / 4059 ms |
| raw | claude-sonnet-5-5 | 81.3% (244/300) | 91.3% (274/300) | 4.3% (13/300) | 11.7% (35/300) | 15.0% (45/300) | – | 0.0 | $0.0017 | 1904 / 2581 ms |
| tools | claude-haiku-5-5 | 82.7% (248/300) | 92.0% (276/300) | 1.0% (3/300) | 11.0% (33/300) | 17.0% (51/300) | – | 1.0 | $0.0003 | 3924 / 5931 ms |
| tools | claude-sonnet-5-5 | 83.7% (251/300) | 92.0% (276/300) | 2.0% (6/300) | 11.3% (34/300) | 15.0% (45/300) | – | 1.0 | $0.0002 | 4363 / 5087 ms |
| verified | claude-haiku-5-5 | 82.7% (248/300) | 92.0% (276/300) | 1.0% (3/300) | 11.0% (33/300) | 17.0% (51/300) | 0 / 0 | 1.0 | $0.0000 | 7470 / 7703 ms |
| verified | claude-sonnet-5-5 | 83.7% (251/300) | 92.3% (277/300) | 1.7% (5/300) | 11.3% (34/300) | 15.3% (46/300) | 0 / 0 | 1.0 | $0.0044 | 3675 / 5234 ms |

## Accuracy by feature

| Feature | #1 claude-haiku-5-5 dev | #5 claude-sonnet-5-5 dev | #7 claude-haiku-5-5 dev | #8 claude-sonnet-5-5 dev | #9 claude-haiku-5-5 dev | #10 claude-sonnet-5-5 dev |
|---|---:|---:|---:|---:|---:|---:|
| Aspect | 100.0% (29/29) | 96.6% (28/29) | 100.0% (29/29) | 100.0% (29/29) | 100.0% (29/29) | 100.0% (29/29) |
| Case | 95.1% (173/182) | 96.2% (175/182) | 97.3% (177/182) | 99.5% (181/182) | 97.3% (177/182) | 99.5% (181/182) |
| Degree | 100.0% (2/2) | 100.0% (2/2) | 100.0% (2/2) | 100.0% (2/2) | 100.0% (2/2) | 100.0% (2/2) |
| Gender | 87.7% (150/171) | 88.9% (152/171) | 90.1% (154/171) | 93.6% (160/171) | 90.1% (154/171) | 93.6% (160/171) |
| Mood | 97.5% (78/80) | 96.2% (77/80) | 97.5% (78/80) | 96.2% (77/80) | 97.5% (78/80) | 96.2% (77/80) |
| Number | 98.5% (256/260) | 98.1% (255/260) | 98.1% (255/260) | 98.8% (257/260) | 98.1% (255/260) | 98.8% (257/260) |
| Person | 100.0% (103/103) | 99.0% (102/103) | 100.0% (103/103) | 100.0% (103/103) | 100.0% (103/103) | 100.0% (103/103) |
| Tense | 96.9% (94/97) | 92.8% (90/97) | 96.9% (94/97) | 95.9% (93/97) | 96.9% (94/97) | 95.9% (93/97) |
| VerbForm | 97.1% (101/104) | 96.2% (100/104) | 96.2% (100/104) | 96.2% (100/104) | 96.2% (100/104) | 96.2% (100/104) |
| Voice | 93.4% (85/91) | 93.4% (85/91) | 95.6% (86/90) | 93.3% (84/90) | 95.6% (86/90) | 93.3% (84/90) |

## Run 1: raw mode, claude-haiku-5-5 on dev

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
| Single-reading forms | 86.7% (78/90) |

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


## Run 5: raw mode, claude-sonnet-5-5 on dev

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
| Single-reading forms | 94.4% (85/90) |

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


## Run 7: tools mode, claude-haiku-5-5 on dev

### By frequency band

| Frequency band | Items | Exact | Lemma | Claim acc. | Halluc. | Unverif. | Schema fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1k-10k | 93 | 86.0% (80/93) | 90.3% (84/93) | 94.6% (88/93) | 1.1% (1/93) | 4.3% (4/93) | 0.0% (0/93) |
| rare | 45 | 77.8% (35/45) | 88.9% (40/45) | 95.6% (43/45) | 0.0% (0/45) | 4.4% (2/45) | 0.0% (0/45) |
| top1k | 162 | 82.1% (133/162) | 93.8% (152/162) | 82.1% (133/162) | 1.2% (2/162) | 16.7% (27/162) | 0.0% (0/162) |

### By pos class

| POS class | Items | Exact | Lemma | Claim acc. | Halluc. | Unverif. | Schema fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| adj | 46 | 80.4% (37/46) | 91.3% (42/46) | 93.5% (43/46) | 0.0% (0/46) | 6.5% (3/46) | 0.0% (0/46) |
| noun | 76 | 86.8% (66/76) | 96.1% (73/76) | 98.7% (75/76) | 0.0% (0/76) | 1.3% (1/76) | 0.0% (0/76) |
| pron_det | 44 | 61.4% (27/44) | 90.9% (40/44) | 100.0% (44/44) | 0.0% (0/44) | 0.0% (0/44) | 0.0% (0/44) |
| uninflected | 30 | 86.7% (26/30) | 86.7% (26/30) | 3.3% (1/30) | 0.0% (0/30) | 96.7% (29/30) | 0.0% (0/30) |
| verb | 104 | 88.5% (92/104) | 91.3% (95/104) | 97.1% (101/104) | 2.9% (3/104) | 0.0% (0/104) | 0.0% (0/104) |

### By classical / ecclesiastical

| Classical / Ecclesiastical | Items | Exact | Lemma | Claim acc. | Halluc. | Unverif. | Schema fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| Classical | 150 | 84.0% (126/150) | 92.0% (138/150) | 87.3% (131/150) | 1.3% (2/150) | 11.3% (17/150) | 0.0% (0/150) |
| Ecclesiastical | 150 | 81.3% (122/150) | 92.0% (138/150) | 88.7% (133/150) | 0.7% (1/150) | 10.7% (16/150) | 0.0% (0/150) |

### Ambiguity handling

| Gold reading in the index | Exact match |
|---|---:|
| Ambiguous forms | 84.5% (131/155) |
| Single-reading forms | 95.6% (86/90) |

### Feature confusions

| Feature: gold → given | Items |
|---|---:|
| Gender: Masc → (none) | 8 |
| Tense: Past → (none) | 3 |
| VerbForm: Part → (none) | 3 |
| Voice: Pass → (none) | 3 |
| Case: Nom → Acc | 2 |
| Gender: Fem,Masc → Neut | 2 |
| Gender: Masc → Fem | 2 |
| Gender: Neut → (none) | 2 |
| Gender: Neut → Masc | 2 |
| Number: Sing → (none) | 2 |
| Case: Abl → (none) | 1 |
| Case: Nom → Voc | 1 |
| Case: Voc → Nom | 1 |
| Gender: Neut → Fem | 1 |
| Mood: Ind → Imp | 1 |
| Mood: Sub → Ind | 1 |
| Number: Plur → (none) | 1 |
| Number: Plur → Sing | 1 |
| Number: Sing → Plur | 1 |
| VerbForm: Gdv → Ger | 1 |
| Voice: Act → (none) | 1 |

### Failure examples

#### Format failure (0)


#### Hallucination (1)


#### Index disagreement (2)


#### Wrong reading (46)


#### Wrong and unverifiable (5)


## Run 8: tools mode, claude-sonnet-5-5 on dev

### By frequency band

| Frequency band | Items | Exact | Lemma | Claim acc. | Halluc. | Unverif. | Schema fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1k-10k | 93 | 88.2% (82/93) | 92.5% (86/93) | 94.6% (88/93) | 1.1% (1/93) | 4.3% (4/93) | 0.0% (0/93) |
| rare | 45 | 75.6% (34/45) | 84.4% (38/45) | 91.1% (41/45) | 2.2% (1/45) | 6.7% (3/45) | 0.0% (0/45) |
| top1k | 162 | 83.3% (135/162) | 93.8% (152/162) | 80.9% (131/162) | 2.5% (4/162) | 16.7% (27/162) | 0.0% (0/162) |

### By pos class

| POS class | Items | Exact | Lemma | Claim acc. | Halluc. | Unverif. | Schema fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| adj | 46 | 78.3% (36/46) | 87.0% (40/46) | 89.1% (41/46) | 2.2% (1/46) | 8.7% (4/46) | 0.0% (0/46) |
| noun | 76 | 88.2% (67/76) | 96.1% (73/76) | 98.7% (75/76) | 0.0% (0/76) | 1.3% (1/76) | 0.0% (0/76) |
| pron_det | 44 | 68.2% (30/44) | 90.9% (40/44) | 95.5% (42/44) | 4.5% (2/44) | 0.0% (0/44) | 0.0% (0/44) |
| uninflected | 30 | 86.7% (26/30) | 86.7% (26/30) | 3.3% (1/30) | 0.0% (0/30) | 96.7% (29/30) | 0.0% (0/30) |
| verb | 104 | 88.5% (92/104) | 93.3% (97/104) | 97.1% (101/104) | 2.9% (3/104) | 0.0% (0/104) | 0.0% (0/104) |

### By classical / ecclesiastical

| Classical / Ecclesiastical | Items | Exact | Lemma | Claim acc. | Halluc. | Unverif. | Schema fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| Classical | 150 | 85.3% (128/150) | 92.0% (138/150) | 86.0% (129/150) | 2.0% (3/150) | 12.0% (18/150) | 0.0% (0/150) |
| Ecclesiastical | 150 | 82.0% (123/150) | 92.0% (138/150) | 87.3% (131/150) | 2.0% (3/150) | 10.7% (16/150) | 0.0% (0/150) |

### Ambiguity handling

| Gold reading in the index | Exact match |
|---|---:|
| Ambiguous forms | 85.8% (133/155) |
| Single-reading forms | 96.7% (87/90) |

### Feature confusions

| Feature: gold → given | Items |
|---|---:|
| Gender: Masc → (none) | 5 |
| Gender: Neut → Masc | 3 |
| Tense: Past → (none) | 3 |
| VerbForm: Part → (none) | 3 |
| Voice: Act → (none) | 3 |
| Voice: Pass → (none) | 3 |
| Mood: Sub → Ind | 2 |
| Number: Plur → Sing | 2 |
| Case: Voc → Nom | 1 |
| Gender: Fem,Masc → (none) | 1 |
| Gender: Fem,Masc → Neut | 1 |
| Gender: Masc → Fem | 1 |
| Mood: Ind → Imp | 1 |
| Number: Sing → Plur | 1 |
| Tense: Past → Fut | 1 |
| VerbForm: Gdv → Ger | 1 |

### Failure examples

#### Format failure (0)


#### Hallucination (4)


#### Index disagreement (2)


#### Wrong reading (39)


#### Wrong and unverifiable (6)


## Run 9: verified mode, claude-haiku-5-5 on dev

### By frequency band

| Frequency band | Items | Exact | Lemma | Claim acc. | Halluc. | Unverif. | Schema fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1k-10k | 93 | 86.0% (80/93) | 90.3% (84/93) | 94.6% (88/93) | 1.1% (1/93) | 4.3% (4/93) | 0.0% (0/93) |
| rare | 45 | 77.8% (35/45) | 88.9% (40/45) | 95.6% (43/45) | 0.0% (0/45) | 4.4% (2/45) | 0.0% (0/45) |
| top1k | 162 | 82.1% (133/162) | 93.8% (152/162) | 82.1% (133/162) | 1.2% (2/162) | 16.7% (27/162) | 0.0% (0/162) |

### By pos class

| POS class | Items | Exact | Lemma | Claim acc. | Halluc. | Unverif. | Schema fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| adj | 46 | 80.4% (37/46) | 91.3% (42/46) | 93.5% (43/46) | 0.0% (0/46) | 6.5% (3/46) | 0.0% (0/46) |
| noun | 76 | 86.8% (66/76) | 96.1% (73/76) | 98.7% (75/76) | 0.0% (0/76) | 1.3% (1/76) | 0.0% (0/76) |
| pron_det | 44 | 61.4% (27/44) | 90.9% (40/44) | 100.0% (44/44) | 0.0% (0/44) | 0.0% (0/44) | 0.0% (0/44) |
| uninflected | 30 | 86.7% (26/30) | 86.7% (26/30) | 3.3% (1/30) | 0.0% (0/30) | 96.7% (29/30) | 0.0% (0/30) |
| verb | 104 | 88.5% (92/104) | 91.3% (95/104) | 97.1% (101/104) | 2.9% (3/104) | 0.0% (0/104) | 0.0% (0/104) |

### By classical / ecclesiastical

| Classical / Ecclesiastical | Items | Exact | Lemma | Claim acc. | Halluc. | Unverif. | Schema fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| Classical | 150 | 84.0% (126/150) | 92.0% (138/150) | 87.3% (131/150) | 1.3% (2/150) | 11.3% (17/150) | 0.0% (0/150) |
| Ecclesiastical | 150 | 81.3% (122/150) | 92.0% (138/150) | 88.7% (133/150) | 0.7% (1/150) | 10.7% (16/150) | 0.0% (0/150) |

### Repair (first pass against final claim)

| Items | Entered repair | Repair success | Repair harm | Net effect |
|---|---:|---:|---:|---:|
| 300 | 1.0% (3/300) | 0 (0.0% (0/3) of repaired) | 0 (0.0% (0/3) of repaired) | +0.0 points |

### Residual error (final claims)

| Final state | Exact | Not exact |
|---|---:|---:|
| verified or ambiguous | 218 correct | 46 false assurance |
| unverifiable | 28 correct, unchecked | 5 unchecked error |
| disputed | 2 false alarm | 1 caught error |

Residual error 17.0% (51/300), false-alarm rate 0.7% (2/300). Read them together: flagging everything would drive the first to zero. An item with no claim is left out of the table, and counts as a miss in exact match.

### Ambiguity handling

| Gold reading in the index | Exact match |
|---|---:|
| Ambiguous forms | 84.5% (131/155) |
| Single-reading forms | 95.6% (86/90) |

### Feature confusions

| Feature: gold → given | Items |
|---|---:|
| Gender: Masc → (none) | 8 |
| Tense: Past → (none) | 3 |
| VerbForm: Part → (none) | 3 |
| Voice: Pass → (none) | 3 |
| Case: Nom → Acc | 2 |
| Gender: Fem,Masc → Neut | 2 |
| Gender: Masc → Fem | 2 |
| Gender: Neut → (none) | 2 |
| Gender: Neut → Masc | 2 |
| Number: Sing → (none) | 2 |
| Case: Abl → (none) | 1 |
| Case: Nom → Voc | 1 |
| Case: Voc → Nom | 1 |
| Gender: Neut → Fem | 1 |
| Mood: Ind → Imp | 1 |
| Mood: Sub → Ind | 1 |
| Number: Plur → (none) | 1 |
| Number: Plur → Sing | 1 |
| Number: Sing → Plur | 1 |
| VerbForm: Gdv → Ger | 1 |
| Voice: Act → (none) | 1 |

### Failure examples

#### Format failure (0)


#### Hallucination (1)


#### Index disagreement (2)


#### Wrong reading (46)


#### Wrong and unverifiable (5)


## Run 10: verified mode, claude-sonnet-5-5 on dev

### By frequency band

| Frequency band | Items | Exact | Lemma | Claim acc. | Halluc. | Unverif. | Schema fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1k-10k | 93 | 88.2% (82/93) | 92.5% (86/93) | 94.6% (88/93) | 1.1% (1/93) | 4.3% (4/93) | 0.0% (0/93) |
| rare | 45 | 75.6% (34/45) | 84.4% (38/45) | 91.1% (41/45) | 2.2% (1/45) | 6.7% (3/45) | 0.0% (0/45) |
| top1k | 162 | 83.3% (135/162) | 94.4% (153/162) | 81.5% (132/162) | 1.9% (3/162) | 16.7% (27/162) | 0.0% (0/162) |

### By pos class

| POS class | Items | Exact | Lemma | Claim acc. | Halluc. | Unverif. | Schema fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| adj | 46 | 78.3% (36/46) | 87.0% (40/46) | 89.1% (41/46) | 2.2% (1/46) | 8.7% (4/46) | 0.0% (0/46) |
| noun | 76 | 88.2% (67/76) | 96.1% (73/76) | 98.7% (75/76) | 0.0% (0/76) | 1.3% (1/76) | 0.0% (0/76) |
| pron_det | 44 | 68.2% (30/44) | 93.2% (41/44) | 97.7% (43/44) | 2.3% (1/44) | 0.0% (0/44) | 0.0% (0/44) |
| uninflected | 30 | 86.7% (26/30) | 86.7% (26/30) | 3.3% (1/30) | 0.0% (0/30) | 96.7% (29/30) | 0.0% (0/30) |
| verb | 104 | 88.5% (92/104) | 93.3% (97/104) | 97.1% (101/104) | 2.9% (3/104) | 0.0% (0/104) | 0.0% (0/104) |

### By classical / ecclesiastical

| Classical / Ecclesiastical | Items | Exact | Lemma | Claim acc. | Halluc. | Unverif. | Schema fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| Classical | 150 | 85.3% (128/150) | 92.0% (138/150) | 86.0% (129/150) | 2.0% (3/150) | 12.0% (18/150) | 0.0% (0/150) |
| Ecclesiastical | 150 | 82.0% (123/150) | 92.7% (139/150) | 88.0% (132/150) | 1.3% (2/150) | 10.7% (16/150) | 0.0% (0/150) |

### Repair (first pass against final claim)

| Items | Entered repair | Repair success | Repair harm | Net effect |
|---|---:|---:|---:|---:|
| 300 | 2.3% (7/300) | 0 (0.0% (0/7) of repaired) | 0 (0.0% (0/7) of repaired) | +0.0 points |

### Residual error (final claims)

| Final state | Exact | Not exact |
|---|---:|---:|
| verified or ambiguous | 221 correct | 40 false assurance |
| unverifiable | 28 correct, unchecked | 6 unchecked error |
| disputed | 2 false alarm | 3 caught error |

Residual error 15.3% (46/300), false-alarm rate 0.7% (2/300). Read them together: flagging everything would drive the first to zero. An item with no claim is left out of the table, and counts as a miss in exact match.

### Ambiguity handling

| Gold reading in the index | Exact match |
|---|---:|
| Ambiguous forms | 85.8% (133/155) |
| Single-reading forms | 96.7% (87/90) |

### Feature confusions

| Feature: gold → given | Items |
|---|---:|
| Gender: Masc → (none) | 5 |
| Gender: Neut → Masc | 3 |
| Tense: Past → (none) | 3 |
| VerbForm: Part → (none) | 3 |
| Voice: Act → (none) | 3 |
| Voice: Pass → (none) | 3 |
| Mood: Sub → Ind | 2 |
| Number: Plur → Sing | 2 |
| Case: Voc → Nom | 1 |
| Gender: Fem,Masc → (none) | 1 |
| Gender: Fem,Masc → Neut | 1 |
| Gender: Masc → Fem | 1 |
| Mood: Ind → Imp | 1 |
| Number: Sing → Plur | 1 |
| Tense: Past → Fut | 1 |
| VerbForm: Gdv → Ger | 1 |

### Failure examples

#### Format failure (0)


#### Hallucination (3)


#### Index disagreement (2)


#### Wrong reading (40)


#### Wrong and unverifiable (6)


## Repair harm

Run 9: 0 item(s) right at first, wrong after repair.

Run 10: 0 item(s) right at first, wrong after repair.
