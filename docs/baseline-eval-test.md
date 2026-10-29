# Eval report

The numbers are averages over a stratified sample that overweights rare lemmas and verbs compared with running text (ADR-003). Claim rates are over the items that gave a claim; exact match, lemma accuracy and the schema-failure rate are over all items; per-feature accuracy is over the answers whose gold marks the feature.

- Run 2: claude-haiku-5-5, raw mode, split test, parse-v1, prompt raw-parse-v3, complete
- Run 3: claude-sonnet-5-5, raw mode, split test, parse-v1, prompt raw-parse-v3, complete
- Run 4: claude-opus-5-5, raw mode, split test, parse-v1, prompt raw-parse-v3, complete

## Headline

| Metric | #2 claude-haiku-5-5 test | #3 claude-sonnet-5-5 test | #4 claude-opus-5-5 test |
|---|---:|---:|---:|
| Items | 1000 | 1000 | 1000 |
| Parse exact match | 79.6% (796/1000) | 83.6% (836/1000) | 86.8% (868/1000) |
| Index matches gold (ceiling) | 79.3% (793/1000) | 79.3% (793/1000) | 79.3% (793/1000) |
| Lemma accuracy | 90.4% (904/1000) | 92.5% (925/1000) | 92.8% (928/1000) |
| Claim accuracy | 78.2% (782/1000) | 80.7% (807/1000) | 81.1% (811/1000) |
| Hallucination rate | 7.5% (75/1000) | 5.9% (59/1000) | 5.9% (59/1000) |
| Unverifiable rate | 14.3% (143/1000) | 13.4% (134/1000) | 13.0% (130/1000) |
| Schema-failure rate | 0.0% (0/1000) | 0.0% (0/1000) | 0.0% (0/1000) |
| Cost | $0.1692 | $1.6539 | $3.7524 |
| Latency p50 / p95 | 2363 / 4355 ms | 1916 / 2879 ms | 2275 / 4241 ms |

## Accuracy by feature

| Feature | #2 claude-haiku-5-5 test | #3 claude-sonnet-5-5 test | #4 claude-opus-5-5 test |
|---|---:|---:|---:|
| Aspect | 100.0% (87/87) | 98.9% (86/87) | 100.0% (87/87) |
| Case | 94.3% (583/618) | 97.7% (604/618) | 98.7% (610/618) |
| Degree | 87.5% (14/16) | 87.5% (14/16) | 87.5% (14/16) |
| Gender | 91.2% (540/592) | 93.2% (552/592) | 94.9% (562/592) |
| Mood | 97.9% (235/240) | 99.2% (238/240) | 98.8% (237/240) |
| Number | 98.6% (837/849) | 99.2% (842/849) | 99.6% (846/849) |
| Person | 100.0% (287/287) | 100.0% (287/287) | 100.0% (287/287) |
| Tense | 94.9% (299/315) | 93.3% (294/315) | 97.1% (306/315) |
| VerbForm | 97.2% (342/352) | 96.3% (339/352) | 97.7% (344/352) |
| Voice | 95.6% (302/316) | 94.3% (298/316) | 94.9% (300/316) |

## Run 2: claude-haiku-5-5 on test

### By frequency band

| Frequency band | Items | Exact | Lemma | Claim acc. | Halluc. | Unverif. | Schema fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1k-10k | 288 | 79.5% (229/288) | 89.2% (257/288) | 87.5% (252/288) | 8.0% (23/288) | 4.5% (13/288) | 0.0% (0/288) |
| rare | 173 | 70.5% (122/173) | 81.5% (141/173) | 65.9% (114/173) | 12.7% (22/173) | 21.4% (37/173) | 0.0% (0/173) |
| top1k | 539 | 82.6% (445/539) | 93.9% (506/539) | 77.2% (416/539) | 5.6% (30/539) | 17.3% (93/539) | 0.0% (0/539) |

### By pos class

| POS class | Items | Exact | Lemma | Claim acc. | Halluc. | Unverif. | Schema fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| adj | 150 | 69.3% (104/150) | 86.0% (129/150) | 79.3% (119/150) | 10.0% (15/150) | 10.7% (16/150) | 0.0% (0/150) |
| noun | 250 | 85.6% (214/250) | 94.4% (236/250) | 94.8% (237/250) | 2.4% (6/250) | 2.8% (7/250) | 0.0% (0/250) |
| pron_det | 150 | 69.3% (104/150) | 90.7% (136/150) | 94.0% (141/150) | 5.3% (8/150) | 0.7% (1/150) | 0.0% (0/150) |
| uninflected | 100 | 91.0% (91/100) | 91.0% (91/100) | 2.0% (2/100) | 1.0% (1/100) | 97.0% (97/100) | 0.0% (0/100) |
| verb | 350 | 80.9% (283/350) | 89.1% (312/350) | 80.9% (283/350) | 12.9% (45/350) | 6.3% (22/350) | 0.0% (0/350) |

### By classical / ecclesiastical

| Classical / Ecclesiastical | Items | Exact | Lemma | Claim acc. | Halluc. | Unverif. | Schema fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| Classical | 500 | 77.8% (389/500) | 89.8% (449/500) | 79.0% (395/500) | 7.2% (36/500) | 13.8% (69/500) | 0.0% (0/500) |
| Ecclesiastical | 500 | 81.4% (407/500) | 91.0% (455/500) | 77.4% (387/500) | 7.8% (39/500) | 14.8% (74/500) | 0.0% (0/500) |

### Ambiguity handling

| Gold reading in the index | Exact match |
|---|---:|
| Ambiguous forms | 74.7% (367/491) |
| Single-reading forms | 95.5% (277/290) |

### Feature confusions

| Feature: gold → given | Items |
|---|---:|
| Gender: Masc → (none) | 18 |
| Case: Nom → Acc | 15 |
| Gender: Fem → Masc | 9 |
| Gender: Neut → Masc | 9 |
| Number: Sing → (none) | 7 |
| Tense: Past → (none) | 6 |
| VerbForm: Part → (none) | 6 |
| Voice: Pass → (none) | 6 |
| Gender: Masc → Neut | 5 |
| Mood: Ind → Sub | 5 |
| Voice: Act → (none) | 5 |
| Case: Nom → (none) | 4 |
| Case: Nom → Abl | 4 |
| Gender: Neut → (none) | 4 |
| Tense: Pres → (none) | 4 |
| Case: Acc → Nom | 3 |
| Gender: Masc → Fem | 3 |
| Number: Sing → Plur | 3 |
| Tense: Fut → Past | 3 |
| Voice: Pass → Act | 3 |
| Case: Gen → Abl | 2 |
| Case: Gen → Dat | 2 |
| Degree: Cmp → (none) | 2 |
| Gender: Fem → Neut | 2 |
| Tense: Fut → Pres | 2 |
| VerbForm: Gdv → Ger | 2 |
| Case: Abl → Gen | 1 |
| Case: Acc → (none) | 1 |
| Case: Dat → Abl | 1 |
| Case: Dat → Gen | 1 |
| Case: Nom → Gen | 1 |
| Gender: Fem → (none) | 1 |
| Gender: Neut → Fem | 1 |
| Number: Plur → (none) | 1 |
| Number: Plur → Sing | 1 |
| Tense: Fut → Pqp | 1 |
| VerbForm: Inf → Fin | 1 |
| VerbForm: Sup → Part | 1 |

### Failure examples

#### Format failure (0)


#### Hallucination (37)


#### Index disagreement (38)


#### Wrong reading (135)


#### Wrong and unverifiable (32)


## Run 3: claude-sonnet-5-5 on test

### By frequency band

| Frequency band | Items | Exact | Lemma | Claim acc. | Halluc. | Unverif. | Schema fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1k-10k | 288 | 85.4% (246/288) | 92.7% (267/288) | 91.7% (264/288) | 4.2% (12/288) | 4.2% (12/288) | 0.0% (0/288) |
| rare | 173 | 74.0% (128/173) | 80.9% (140/173) | 69.4% (120/173) | 10.4% (18/173) | 20.2% (35/173) | 0.0% (0/173) |
| top1k | 539 | 85.7% (462/539) | 96.1% (518/539) | 78.5% (423/539) | 5.4% (29/539) | 16.1% (87/539) | 0.0% (0/539) |

### By pos class

| POS class | Items | Exact | Lemma | Claim acc. | Halluc. | Unverif. | Schema fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| adj | 150 | 78.0% (117/150) | 92.0% (138/150) | 88.0% (132/150) | 3.3% (5/150) | 8.7% (13/150) | 0.0% (0/150) |
| noun | 250 | 89.2% (223/250) | 94.8% (237/250) | 95.6% (239/250) | 2.0% (5/250) | 2.4% (6/250) | 0.0% (0/250) |
| pron_det | 150 | 74.0% (111/150) | 94.0% (141/150) | 94.0% (141/150) | 6.0% (9/150) | 0.0% (0/150) | 0.0% (0/150) |
| uninflected | 100 | 91.0% (91/100) | 92.0% (92/100) | 2.0% (2/100) | 1.0% (1/100) | 97.0% (97/100) | 0.0% (0/100) |
| verb | 350 | 84.0% (294/350) | 90.6% (317/350) | 83.7% (293/350) | 11.1% (39/350) | 5.1% (18/350) | 0.0% (0/350) |

### By classical / ecclesiastical

| Classical / Ecclesiastical | Items | Exact | Lemma | Claim acc. | Halluc. | Unverif. | Schema fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| Classical | 500 | 82.4% (412/500) | 92.6% (463/500) | 80.8% (404/500) | 6.0% (30/500) | 13.2% (66/500) | 0.0% (0/500) |
| Ecclesiastical | 500 | 84.8% (424/500) | 92.4% (462/500) | 80.6% (403/500) | 5.8% (29/500) | 13.6% (68/500) | 0.0% (0/500) |

### Ambiguity handling

| Gold reading in the index | Exact match |
|---|---:|
| Ambiguous forms | 82.7% (406/491) |
| Single-reading forms | 95.9% (278/290) |

### Feature confusions

| Feature: gold → given | Items |
|---|---:|
| Gender: Masc → (none) | 19 |
| VerbForm: Part → (none) | 12 |
| Gender: Fem → Masc | 9 |
| Tense: Past → (none) | 9 |
| Voice: Pass → (none) | 9 |
| Tense: Pres → (none) | 8 |
| Voice: Act → (none) | 6 |
| Case: Nom → Acc | 5 |
| Gender: Neut → Masc | 5 |
| Number: Sing → (none) | 4 |
| Case: Acc → Nom | 3 |
| Gender: Masc → Neut | 3 |
| Voice: Pass → Act | 3 |
| Case: Dat → Abl | 2 |
| Degree: Cmp → (none) | 2 |
| Gender: Fem → Neut | 2 |
| Number: Sing → Plur | 2 |
| Aspect: Perf → (none) | 1 |
| Case: Acc → (none) | 1 |
| Case: Gen → Dat | 1 |
| Case: Nom → (none) | 1 |
| Case: Nom → Abl | 1 |
| Gender: Masc → Fem | 1 |
| Gender: Neut → (none) | 1 |
| Mood: Ind → Sub | 1 |
| Mood: Sub → Ind | 1 |
| Number: Plur → (none) | 1 |
| Tense: Fut → (none) | 1 |
| Tense: Fut → Pqp | 1 |
| Tense: Past → Fut | 1 |
| Tense: Past → Pres | 1 |
| VerbForm: Gdv → Ger | 1 |

### Failure examples

#### Format failure (0)


#### Hallucination (24)


#### Index disagreement (35)


#### Wrong reading (117)


#### Wrong and unverifiable (23)


## Run 4: claude-opus-5-5 on test

### By frequency band

| Frequency band | Items | Exact | Lemma | Claim acc. | Halluc. | Unverif. | Schema fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1k-10k | 288 | 87.2% (251/288) | 90.6% (261/288) | 89.9% (259/288) | 6.2% (18/288) | 3.8% (11/288) | 0.0% (0/288) |
| rare | 173 | 79.8% (138/173) | 85.0% (147/173) | 73.4% (127/173) | 9.8% (17/173) | 16.8% (29/173) | 0.0% (0/173) |
| top1k | 539 | 88.9% (479/539) | 96.5% (520/539) | 78.8% (425/539) | 4.5% (24/539) | 16.7% (90/539) | 0.0% (0/539) |

### By pos class

| POS class | Items | Exact | Lemma | Claim acc. | Halluc. | Unverif. | Schema fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| adj | 150 | 79.3% (119/150) | 90.7% (136/150) | 88.0% (132/150) | 5.3% (8/150) | 6.7% (10/150) | 0.0% (0/150) |
| noun | 250 | 90.4% (226/250) | 94.4% (236/250) | 96.4% (241/250) | 1.2% (3/250) | 2.4% (6/250) | 0.0% (0/250) |
| pron_det | 150 | 81.3% (122/150) | 92.0% (138/150) | 94.0% (141/150) | 5.3% (8/150) | 0.7% (1/150) | 0.0% (0/150) |
| uninflected | 100 | 96.0% (96/100) | 97.0% (97/100) | 0.0% (0/100) | 1.0% (1/100) | 99.0% (99/100) | 0.0% (0/100) |
| verb | 350 | 87.1% (305/350) | 91.7% (321/350) | 84.9% (297/350) | 11.1% (39/350) | 4.0% (14/350) | 0.0% (0/350) |

### By classical / ecclesiastical

| Classical / Ecclesiastical | Items | Exact | Lemma | Claim acc. | Halluc. | Unverif. | Schema fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| Classical | 500 | 87.6% (438/500) | 93.4% (467/500) | 80.6% (403/500) | 6.6% (33/500) | 12.8% (64/500) | 0.0% (0/500) |
| Ecclesiastical | 500 | 86.0% (430/500) | 92.2% (461/500) | 81.6% (408/500) | 5.2% (26/500) | 13.2% (66/500) | 0.0% (0/500) |

### Ambiguity handling

| Gold reading in the index | Exact match |
|---|---:|
| Ambiguous forms | 86.8% (426/491) |
| Single-reading forms | 96.2% (279/290) |

### Feature confusions

| Feature: gold → given | Items |
|---|---:|
| Gender: Masc → (none) | 11 |
| Voice: Act → (none) | 10 |
| Gender: Fem → Masc | 7 |
| VerbForm: Part → (none) | 7 |
| Tense: Past → (none) | 6 |
| Voice: Pass → (none) | 6 |
| Gender: Neut → Masc | 5 |
| Case: Acc → Nom | 3 |
| Gender: Masc → Neut | 3 |
| Case: Nom → Acc | 2 |
| Degree: Cmp → (none) | 2 |
| Gender: Fem → Neut | 2 |
| Mood: Ind → Sub | 2 |
| Number: Sing → Plur | 2 |
| Case: Acc → (none) | 1 |
| Case: Gen → Dat | 1 |
| Case: Nom → Voc | 1 |
| Gender: Masc → Fem | 1 |
| Gender: Neut → (none) | 1 |
| Mood: Sub → Ind | 1 |
| Number: Sing → (none) | 1 |
| Tense: Fut → Past | 1 |
| Tense: Fut → Pqp | 1 |
| Tense: Past → Fut | 1 |
| VerbForm: Gdv → Ger | 1 |

### Failure examples

#### Format failure (0)


#### Hallucination (21)


#### Index disagreement (38)


#### Wrong reading (97)


#### Wrong and unverifiable (14)
