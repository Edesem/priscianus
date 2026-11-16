# Eval report

The numbers are averages over a stratified sample that overweights rare lemmas and verbs compared with running text (ADR-003). Claim rates are over the items that gave a claim; exact match, lemma accuracy and the schema-failure rate are over all items; per-feature accuracy is over the answers whose gold marks the feature.

- Run 2: claude-haiku-5-5, raw mode, split test, parse-v1, prompt raw-parse-v3, complete
- Run 3: claude-sonnet-5-5, raw mode, split test, parse-v1, prompt raw-parse-v3, complete
- Run 11: claude-haiku-5-5, tools mode, split test, parse-v1, prompt tools-parse-v1, complete
- Run 12: claude-sonnet-5-5, tools mode, split test, parse-v1, prompt tools-parse-v1, complete
- Run 13: claude-haiku-5-5, verified mode, split test, parse-v1, prompt verified-parse-v1, complete
- Run 14: claude-sonnet-5-5, verified mode, split test, parse-v1, prompt verified-parse-v1, complete

## Headline

| Metric | #2 claude-haiku-5-5 test | #3 claude-sonnet-5-5 test | #11 claude-haiku-5-5 test | #12 claude-sonnet-5-5 test | #13 claude-haiku-5-5 test | #14 claude-sonnet-5-5 test |
|---|---:|---:|---:|---:|---:|---:|
| Items | 1000 | 1000 | 1000 | 1000 | 1000 | 1000 |
| Parse exact match | 79.6% (796/1000) | 83.6% (836/1000) | 82.4% (824/1000) | 86.9% (869/1000) | 82.8% (828/1000) | 86.8% (868/1000) |
| Index matches gold (ceiling) | 79.8% (798/1000) | 79.8% (798/1000) | 79.8% (798/1000) | 79.8% (798/1000) | 79.8% (798/1000) | 79.8% (798/1000) |
| Lemma accuracy | 90.4% (904/1000) | 92.5% (925/1000) | 91.7% (917/1000) | 93.3% (933/1000) | 91.8% (918/1000) | 93.5% (935/1000) |
| Claim accuracy | 78.2% (782/1000) | 80.7% (807/1000) | 82.5% (825/1000) | 82.9% (829/1000) | 83.0% (830/1000) | 83.1% (831/1000) |
| Hallucination rate | 7.5% (75/1000) | 5.9% (59/1000) | 4.7% (47/1000) | 4.8% (48/1000) | 4.3% (43/1000) | 4.6% (46/1000) |
| Unverifiable rate | 14.3% (143/1000) | 13.4% (134/1000) | 12.8% (128/1000) | 12.3% (123/1000) | 12.7% (127/1000) | 12.3% (123/1000) |
| Schema-failure rate | 0.0% (0/1000) | 0.0% (0/1000) | 0.0% (0/1000) | 0.0% (0/1000) | 0.0% (0/1000) | 0.0% (0/1000) |
| Cost | $0.1692 | $1.6539 | $0.3179 | $4.4060 | $0.0204 | $0.3444 |
| Latency p50 / p95 | 2363 / 4355 ms | 1916 / 2879 ms | 3785 / 6089 ms | 3449 / 5281 ms | 7816 / 11830 ms | 6922 / 11469 ms |

## Modes compared

| Mode | Model | Exact | Lemma | Halluc. | Unverif. | Residual error | Repair success / harm | Tool calls / item | $ / item | Latency p50 / p95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| raw | claude-haiku-5-5 | 79.6% (796/1000) | 90.4% (904/1000) | 7.5% (75/1000) | 14.3% (143/1000) | 16.7% (167/1000) | – | 0.0 | $0.0002 | 2363 / 4355 ms |
| raw | claude-sonnet-5-5 | 83.6% (836/1000) | 92.5% (925/1000) | 5.9% (59/1000) | 13.4% (134/1000) | 14.0% (140/1000) | – | 0.0 | $0.0017 | 1916 / 2879 ms |
| tools | claude-haiku-5-5 | 82.4% (824/1000) | 91.7% (917/1000) | 4.7% (47/1000) | 12.8% (128/1000) | 15.5% (155/1000) | – | 1.0 | $0.0003 | 3785 / 6089 ms |
| tools | claude-sonnet-5-5 | 86.9% (869/1000) | 93.3% (933/1000) | 4.8% (48/1000) | 12.3% (123/1000) | 11.4% (114/1000) | – | 1.0 | $0.0044 | 3449 / 5281 ms |
| verified | claude-haiku-5-5 | 82.8% (828/1000) | 91.8% (918/1000) | 4.3% (43/1000) | 12.7% (127/1000) | 15.4% (154/1000) | 4 / 0 | 1.0 | $0.0000 | 7816 / 11830 ms |
| verified | claude-sonnet-5-5 | 86.8% (868/1000) | 93.5% (935/1000) | 4.6% (46/1000) | 12.3% (123/1000) | 11.6% (116/1000) | 0 / 1 | 1.0 | $0.0003 | 6922 / 11469 ms |

## Accuracy by feature

| Feature | #2 claude-haiku-5-5 test | #3 claude-sonnet-5-5 test | #11 claude-haiku-5-5 test | #12 claude-sonnet-5-5 test | #13 claude-haiku-5-5 test | #14 claude-sonnet-5-5 test |
|---|---:|---:|---:|---:|---:|---:|
| Aspect | 100.0% (87/87) | 98.9% (86/87) | 100.0% (87/87) | 100.0% (87/87) | 100.0% (87/87) | 100.0% (87/87) |
| Case | 94.3% (583/618) | 97.7% (604/618) | 96.6% (597/618) | 98.5% (609/618) | 96.9% (599/618) | 98.5% (609/618) |
| Degree | 87.5% (14/16) | 87.5% (14/16) | 87.5% (14/16) | 93.8% (15/16) | 87.5% (14/16) | 93.8% (15/16) |
| Gender | 91.2% (540/592) | 93.2% (552/592) | 92.6% (548/592) | 94.9% (562/592) | 92.7% (549/592) | 94.8% (561/592) |
| Mood | 97.9% (235/240) | 99.2% (238/240) | 98.8% (237/240) | 99.2% (238/240) | 98.8% (237/240) | 99.2% (238/240) |
| Number | 98.6% (837/849) | 99.2% (842/849) | 99.2% (842/849) | 99.6% (846/849) | 99.2% (842/849) | 99.6% (846/849) |
| Person | 100.0% (287/287) | 100.0% (287/287) | 99.7% (286/287) | 100.0% (287/287) | 99.7% (286/287) | 100.0% (287/287) |
| Tense | 94.9% (299/315) | 93.3% (294/315) | 97.1% (306/315) | 97.1% (306/315) | 97.1% (306/315) | 97.1% (306/315) |
| VerbForm | 97.2% (342/352) | 96.3% (339/352) | 97.2% (342/352) | 97.7% (344/352) | 97.4% (343/352) | 97.4% (343/352) |
| Voice | 95.6% (302/316) | 94.3% (298/316) | 93.7% (296/316) | 94.0% (297/316) | 93.7% (296/316) | 94.0% (297/316) |

## Run 2: raw mode, claude-haiku-5-5 on test

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
| Ambiguous forms | 74.6% (367/492) |
| Single-reading forms | 95.2% (280/294) |

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


## Run 3: raw mode, claude-sonnet-5-5 on test

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
| Ambiguous forms | 82.5% (406/492) |
| Single-reading forms | 95.2% (280/294) |

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


## Run 11: tools mode, claude-haiku-5-5 on test

### By frequency band

| Frequency band | Items | Exact | Lemma | Claim acc. | Halluc. | Unverif. | Schema fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1k-10k | 288 | 84.7% (244/288) | 91.3% (263/288) | 90.3% (260/288) | 6.2% (18/288) | 3.5% (10/288) | 0.0% (0/288) |
| rare | 173 | 76.3% (132/173) | 83.8% (145/173) | 76.3% (132/173) | 8.1% (14/173) | 15.6% (27/173) | 0.0% (0/173) |
| top1k | 539 | 83.1% (448/539) | 94.4% (509/539) | 80.3% (433/539) | 2.8% (15/539) | 16.9% (91/539) | 0.0% (0/539) |

### By pos class

| POS class | Items | Exact | Lemma | Claim acc. | Halluc. | Unverif. | Schema fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| adj | 150 | 74.0% (111/150) | 86.7% (130/150) | 87.3% (131/150) | 5.3% (8/150) | 7.3% (11/150) | 0.0% (0/150) |
| noun | 250 | 89.2% (223/250) | 96.0% (240/250) | 97.2% (243/250) | 1.6% (4/250) | 1.2% (3/250) | 0.0% (0/250) |
| pron_det | 150 | 70.0% (105/150) | 93.3% (140/150) | 98.7% (148/150) | 1.3% (2/150) | 0.0% (0/150) | 0.0% (0/150) |
| uninflected | 100 | 91.0% (91/100) | 92.0% (92/100) | 1.0% (1/100) | 1.0% (1/100) | 98.0% (98/100) | 0.0% (0/100) |
| verb | 350 | 84.0% (294/350) | 90.0% (315/350) | 86.3% (302/350) | 9.1% (32/350) | 4.6% (16/350) | 0.0% (0/350) |

### By classical / ecclesiastical

| Classical / Ecclesiastical | Items | Exact | Lemma | Claim acc. | Halluc. | Unverif. | Schema fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| Classical | 500 | 81.0% (405/500) | 91.0% (455/500) | 83.2% (416/500) | 4.4% (22/500) | 12.4% (62/500) | 0.0% (0/500) |
| Ecclesiastical | 500 | 83.8% (419/500) | 92.4% (462/500) | 81.8% (409/500) | 5.0% (25/500) | 13.2% (66/500) | 0.0% (0/500) |

### Ambiguity handling

| Gold reading in the index | Exact match |
|---|---:|
| Ambiguous forms | 80.9% (398/492) |
| Single-reading forms | 97.3% (286/294) |

### Feature confusions

| Feature: gold → given | Items |
|---|---:|
| Gender: Masc → (none) | 18 |
| Case: Nom → Acc | 9 |
| Voice: Act → (none) | 8 |
| Gender: Fem → Masc | 7 |
| Gender: Neut → Masc | 7 |
| Voice: Pass → Act | 7 |
| VerbForm: Part → (none) | 6 |
| Gender: Masc → Neut | 5 |
| Tense: Past → (none) | 5 |
| Voice: Pass → (none) | 5 |
| Gender: Masc → Fem | 3 |
| Gender: Neut → (none) | 3 |
| Number: Sing → (none) | 3 |
| Case: Acc → Abl | 2 |
| Case: Acc → Nom | 2 |
| Case: Nom → (none) | 2 |
| Degree: Cmp → (none) | 2 |
| Mood: Ind → Sub | 2 |
| Number: Sing → Plur | 2 |
| VerbForm: Gdv → Ger | 2 |
| Case: Abl → Dat | 1 |
| Case: Abl → Nom | 1 |
| Case: Dat → Nom | 1 |
| Case: Gen → Abl | 1 |
| Case: Gen → Dat | 1 |
| Case: Nom → Abl | 1 |
| Gender: Fem → Neut | 1 |
| Mood: Sub → Ind | 1 |
| Number: Plur → (none) | 1 |
| Number: Plur → Sing | 1 |
| Person: 3 → (none) | 1 |
| Tense: Fut → Past | 1 |
| Tense: Fut → Pqp | 1 |
| Tense: Past → Fut | 1 |
| Tense: Past → Pres | 1 |
| VerbForm: Part → Fin | 1 |
| VerbForm: Sup → Part | 1 |

### Failure examples

#### Format failure (0)


#### Hallucination (21)


#### Index disagreement (26)


#### Wrong reading (134)


#### Wrong and unverifiable (21)


## Run 12: tools mode, claude-sonnet-5-5 on test

### By frequency band

| Frequency band | Items | Exact | Lemma | Claim acc. | Halluc. | Unverif. | Schema fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1k-10k | 288 | 90.3% (260/288) | 93.8% (270/288) | 92.0% (265/288) | 4.5% (13/288) | 3.5% (10/288) | 0.0% (0/288) |
| rare | 173 | 79.8% (138/173) | 84.4% (146/173) | 78.0% (135/173) | 7.5% (13/173) | 14.5% (25/173) | 0.0% (0/173) |
| top1k | 539 | 87.4% (471/539) | 95.9% (517/539) | 79.6% (429/539) | 4.1% (22/539) | 16.3% (88/539) | 0.0% (0/539) |

### By pos class

| POS class | Items | Exact | Lemma | Claim acc. | Halluc. | Unverif. | Schema fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| adj | 150 | 82.0% (123/150) | 90.7% (136/150) | 90.0% (135/150) | 4.0% (6/150) | 6.0% (9/150) | 0.0% (0/150) |
| noun | 250 | 91.2% (228/250) | 95.6% (239/250) | 97.6% (244/250) | 0.8% (2/250) | 1.6% (4/250) | 0.0% (0/250) |
| pron_det | 150 | 76.7% (115/150) | 94.0% (141/150) | 95.3% (143/150) | 4.7% (7/150) | 0.0% (0/150) | 0.0% (0/150) |
| uninflected | 100 | 92.0% (92/100) | 93.0% (93/100) | 2.0% (2/100) | 1.0% (1/100) | 97.0% (97/100) | 0.0% (0/100) |
| verb | 350 | 88.9% (311/350) | 92.6% (324/350) | 87.1% (305/350) | 9.1% (32/350) | 3.7% (13/350) | 0.0% (0/350) |

### By classical / ecclesiastical

| Classical / Ecclesiastical | Items | Exact | Lemma | Claim acc. | Halluc. | Unverif. | Schema fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| Classical | 500 | 86.4% (432/500) | 93.2% (466/500) | 82.6% (413/500) | 5.4% (27/500) | 12.0% (60/500) | 0.0% (0/500) |
| Ecclesiastical | 500 | 87.4% (437/500) | 93.4% (467/500) | 83.2% (416/500) | 4.2% (21/500) | 12.6% (63/500) | 0.0% (0/500) |

### Ambiguity handling

| Gold reading in the index | Exact match |
|---|---:|
| Ambiguous forms | 88.2% (434/492) |
| Single-reading forms | 98.3% (289/294) |

### Feature confusions

| Feature: gold → given | Items |
|---|---:|
| Gender: Masc → (none) | 12 |
| Gender: Fem → Masc | 7 |
| Tense: Past → (none) | 7 |
| VerbForm: Part → (none) | 7 |
| Voice: Pass → (none) | 7 |
| Voice: Act → (none) | 6 |
| Voice: Pass → Act | 6 |
| Gender: Masc → Neut | 4 |
| Case: Nom → Acc | 3 |
| Gender: Neut → Masc | 3 |
| Case: Acc → Nom | 2 |
| Gender: Neut → (none) | 2 |
| Number: Sing → (none) | 2 |
| Case: Gen → Dat | 1 |
| Case: Nom → (none) | 1 |
| Case: Nom → Abl | 1 |
| Case: Nom → Voc | 1 |
| Degree: Cmp → (none) | 1 |
| Gender: Fem → Neut | 1 |
| Gender: Masc → Fem | 1 |
| Mood: Ind → Sub | 1 |
| Mood: Sub → Ind | 1 |
| Number: Sing → Plur | 1 |
| Tense: Fut → Pqp | 1 |
| Tense: Past → Fut | 1 |
| VerbForm: Gdv → Ger | 1 |

### Failure examples

#### Format failure (0)


#### Hallucination (17)


#### Index disagreement (31)


#### Wrong reading (98)


#### Wrong and unverifiable (16)


## Run 13: verified mode, claude-haiku-5-5 on test

### By frequency band

| Frequency band | Items | Exact | Lemma | Claim acc. | Halluc. | Unverif. | Schema fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1k-10k | 288 | 85.4% (246/288) | 91.3% (263/288) | 91.3% (263/288) | 5.2% (15/288) | 3.5% (10/288) | 0.0% (0/288) |
| rare | 173 | 76.9% (133/173) | 84.4% (146/173) | 76.9% (133/173) | 8.1% (14/173) | 15.0% (26/173) | 0.0% (0/173) |
| top1k | 539 | 83.3% (449/539) | 94.4% (509/539) | 80.5% (434/539) | 2.6% (14/539) | 16.9% (91/539) | 0.0% (0/539) |

### By pos class

| POS class | Items | Exact | Lemma | Claim acc. | Halluc. | Unverif. | Schema fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| adj | 150 | 76.0% (114/150) | 87.3% (131/150) | 89.3% (134/150) | 4.0% (6/150) | 6.7% (10/150) | 0.0% (0/150) |
| noun | 250 | 89.2% (223/250) | 96.0% (240/250) | 97.2% (243/250) | 1.6% (4/250) | 1.2% (3/250) | 0.0% (0/250) |
| pron_det | 150 | 70.0% (105/150) | 93.3% (140/150) | 98.7% (148/150) | 1.3% (2/150) | 0.0% (0/150) | 0.0% (0/150) |
| uninflected | 100 | 91.0% (91/100) | 92.0% (92/100) | 1.0% (1/100) | 1.0% (1/100) | 98.0% (98/100) | 0.0% (0/100) |
| verb | 350 | 84.3% (295/350) | 90.0% (315/350) | 86.9% (304/350) | 8.6% (30/350) | 4.6% (16/350) | 0.0% (0/350) |

### By classical / ecclesiastical

| Classical / Ecclesiastical | Items | Exact | Lemma | Claim acc. | Halluc. | Unverif. | Schema fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| Classical | 500 | 81.4% (407/500) | 91.2% (456/500) | 83.6% (418/500) | 4.2% (21/500) | 12.2% (61/500) | 0.0% (0/500) |
| Ecclesiastical | 500 | 84.2% (421/500) | 92.4% (462/500) | 82.4% (412/500) | 4.4% (22/500) | 13.2% (66/500) | 0.0% (0/500) |

### Repair (first pass against final claim)

| Items | Entered repair | Repair success | Repair harm | Net effect |
|---|---:|---:|---:|---:|
| 1000 | 4.7% (47/1000) | 4 (8.5% (4/47) of repaired) | 0 (0.0% (0/47) of repaired) | +0.4 points |

### Residual error (final claims)

| Final state | Exact | Not exact |
|---|---:|---:|
| verified or ambiguous | 696 correct | 134 false assurance |
| unverifiable | 107 correct, unchecked | 20 unchecked error |
| disputed | 25 false alarm | 18 caught error |

Residual error 15.4% (154/1000), false-alarm rate 2.5% (25/1000). Read them together: flagging everything would drive the first to zero. An item with no claim is left out of the table, and counts as a miss in exact match.

### Ambiguity handling

| Gold reading in the index | Exact match |
|---|---:|
| Ambiguous forms | 81.7% (402/492) |
| Single-reading forms | 97.3% (286/294) |

### Feature confusions

| Feature: gold → given | Items |
|---|---:|
| Gender: Masc → (none) | 17 |
| Case: Nom → Acc | 9 |
| Voice: Act → (none) | 8 |
| Gender: Fem → Masc | 7 |
| Gender: Neut → Masc | 7 |
| Voice: Pass → Act | 7 |
| VerbForm: Part → (none) | 6 |
| Gender: Masc → Neut | 5 |
| Tense: Past → (none) | 5 |
| Voice: Pass → (none) | 5 |
| Gender: Masc → Fem | 3 |
| Gender: Neut → (none) | 3 |
| Number: Sing → (none) | 3 |
| Case: Acc → Nom | 2 |
| Case: Nom → (none) | 2 |
| Degree: Cmp → (none) | 2 |
| Mood: Ind → Sub | 2 |
| Number: Sing → Plur | 2 |
| Case: Abl → Dat | 1 |
| Case: Abl → Nom | 1 |
| Case: Acc → Abl | 1 |
| Case: Dat → Nom | 1 |
| Case: Gen → Dat | 1 |
| Case: Nom → Abl | 1 |
| Gender: Fem → Neut | 1 |
| Mood: Sub → Ind | 1 |
| Number: Plur → (none) | 1 |
| Number: Plur → Sing | 1 |
| Person: 3 → (none) | 1 |
| Tense: Fut → Past | 1 |
| Tense: Fut → Pqp | 1 |
| Tense: Past → Fut | 1 |
| Tense: Past → Pres | 1 |
| VerbForm: Gdv → Ger | 1 |
| VerbForm: Part → Fin | 1 |
| VerbForm: Sup → Part | 1 |

### Failure examples

#### Format failure (0)


#### Hallucination (18)


#### Index disagreement (25)


#### Wrong reading (134)


#### Wrong and unverifiable (20)


## Run 14: verified mode, claude-sonnet-5-5 on test

### By frequency band

| Frequency band | Items | Exact | Lemma | Claim acc. | Halluc. | Unverif. | Schema fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1k-10k | 288 | 89.9% (259/288) | 93.8% (270/288) | 92.0% (265/288) | 4.5% (13/288) | 3.5% (10/288) | 0.0% (0/288) |
| rare | 173 | 79.8% (138/173) | 84.4% (146/173) | 78.0% (135/173) | 7.5% (13/173) | 14.5% (25/173) | 0.0% (0/173) |
| top1k | 539 | 87.4% (471/539) | 96.3% (519/539) | 80.0% (431/539) | 3.7% (20/539) | 16.3% (88/539) | 0.0% (0/539) |

### By pos class

| POS class | Items | Exact | Lemma | Claim acc. | Halluc. | Unverif. | Schema fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| adj | 150 | 82.0% (123/150) | 91.3% (137/150) | 90.7% (136/150) | 3.3% (5/150) | 6.0% (9/150) | 0.0% (0/150) |
| noun | 250 | 91.2% (228/250) | 95.6% (239/250) | 97.6% (244/250) | 0.8% (2/250) | 1.6% (4/250) | 0.0% (0/250) |
| pron_det | 150 | 76.7% (115/150) | 94.7% (142/150) | 96.0% (144/150) | 4.0% (6/150) | 0.0% (0/150) | 0.0% (0/150) |
| uninflected | 100 | 92.0% (92/100) | 93.0% (93/100) | 2.0% (2/100) | 1.0% (1/100) | 97.0% (97/100) | 0.0% (0/100) |
| verb | 350 | 88.6% (310/350) | 92.6% (324/350) | 87.1% (305/350) | 9.1% (32/350) | 3.7% (13/350) | 0.0% (0/350) |

### By classical / ecclesiastical

| Classical / Ecclesiastical | Items | Exact | Lemma | Claim acc. | Halluc. | Unverif. | Schema fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| Classical | 500 | 86.2% (431/500) | 93.4% (467/500) | 82.8% (414/500) | 5.2% (26/500) | 12.0% (60/500) | 0.0% (0/500) |
| Ecclesiastical | 500 | 87.4% (437/500) | 93.6% (468/500) | 83.4% (417/500) | 4.0% (20/500) | 12.6% (63/500) | 0.0% (0/500) |

### Repair (first pass against final claim)

| Items | Entered repair | Repair success | Repair harm | Net effect |
|---|---:|---:|---:|---:|
| 1000 | 4.4% (44/1000) | 0 (0.0% (0/44) of repaired) | 1 (2.3% (1/44) of repaired) | -0.1 points |

### Residual error (final claims)

| Final state | Exact | Not exact |
|---|---:|---:|
| verified or ambiguous | 731 correct | 100 false assurance |
| unverifiable | 107 correct, unchecked | 16 unchecked error |
| disputed | 30 false alarm | 16 caught error |

Residual error 11.6% (116/1000), false-alarm rate 3.0% (30/1000). Read them together: flagging everything would drive the first to zero. An item with no claim is left out of the table, and counts as a miss in exact match.

### Ambiguity handling

| Gold reading in the index | Exact match |
|---|---:|
| Ambiguous forms | 88.2% (434/492) |
| Single-reading forms | 98.3% (289/294) |

### Feature confusions

| Feature: gold → given | Items |
|---|---:|
| Gender: Masc → (none) | 12 |
| VerbForm: Part → (none) | 8 |
| Gender: Fem → Masc | 7 |
| Tense: Past → (none) | 7 |
| Voice: Pass → (none) | 7 |
| Voice: Act → (none) | 6 |
| Voice: Pass → Act | 6 |
| Gender: Masc → Neut | 4 |
| Gender: Neut → Masc | 4 |
| Case: Nom → Acc | 3 |
| Case: Acc → Nom | 2 |
| Gender: Neut → (none) | 2 |
| Number: Sing → (none) | 2 |
| Case: Gen → Dat | 1 |
| Case: Nom → (none) | 1 |
| Case: Nom → Abl | 1 |
| Case: Nom → Voc | 1 |
| Degree: Cmp → (none) | 1 |
| Gender: Fem → Neut | 1 |
| Gender: Masc → Fem | 1 |
| Mood: Ind → Sub | 1 |
| Mood: Sub → Ind | 1 |
| Number: Sing → Plur | 1 |
| Tense: Fut → Pqp | 1 |
| Tense: Past → Fut | 1 |
| VerbForm: Gdv → Ger | 1 |

### Failure examples

#### Format failure (0)


#### Hallucination (16)


#### Index disagreement (30)


#### Wrong reading (100)


#### Wrong and unverifiable (16)


## Repair harm

Run 13: 0 item(s) right at first, wrong after repair.

Run 14: 1 item(s) right at first, wrong after repair.
- **perseus/phi0972.phi001.perseus-lat1.xml@774/3** — index: strictus verb Aspect=Perf|Case=Dat|Gender=Masc|Number=Sing|Tense=Past|VerbForm=Part|Voice=Pass; strictus verb Aspect=Perf|Case=Dat|Gender=Neut|Number=Sing|Tense=Past|VerbForm=Part|Voice=Pass; strictus verb Aspect=Perf|Case=Abl|Gender=Masc|Number=Sing|Tense=Past|VerbForm=Part|Voice=Pass; strictus verb Aspect=Perf|Case=Abl|Gender=Neut|Number=Sing|Tense=Past|VerbForm=Part|Voice=Pass
