# Parse set v1

The gold parse set for the baseline eval ([ADR-003](adr/ADR-003.md), Decisions 3 to 5). It is frozen: `parse-v1` is never rebuilt, and any change makes `parse-v2`.

- **Manifest:** `src/data/eval_sets/parse-v1.jsonl`, one row per item: IDs, strata and SHA-256 hashes of the form and the sentence. No treebank text.
- **Meta:** `src/data/eval_sets/parse-v1.meta.json`: seed (39), quotas, UD release (r2.18), checksums of the treebank files used, candidate counts per cell, and any shortfalls (none).
- **Source:** the test splits of Perseus, PROIEL and ITTB. Frequency bands come from the train splits of all six UD Latin treebanks, computed by `build-set`.

## Rebuild or check

```
make eval-data                                              # download UD r2.18
cd src/evals && uv run python -m evals build-set --set parse --version v1   # refuses: v1 is frozen
```

`evals.parse_set.load_parse_set(manifest, ud_dir)` joins the manifest to the downloaded files and raises `ManifestMismatchError` if a file or item is missing or a hash differs, which means the files are not UD r2.18.

## Counts

Items per stratum and split. Closed classes (pron/det, uninflected) are not divided by band. Test has 1,000 items and dev 300; a sentence supplies one item across both. Dev and test draw on the same candidates, test first, so a short cell (Ecclesiastical rare verbs: 28 test, 0 dev) is filled for test and handed to the next band for dev.

| Slice | Class | Band | Test | Dev |
|---|---|---|---|---|
| Classical | verb | top1k | 70 | 21 |
| Classical | verb | 1k-10k | 61 | 18 |
| Classical | verb | rare | 44 | 13 |
| Classical | noun | top1k | 50 | 15 |
| Classical | noun | 1k-10k | 44 | 13 |
| Classical | noun | rare | 31 | 10 |
| Classical | adj | top1k | 30 | 9 |
| Classical | adj | 1k-10k | 26 | 8 |
| Classical | adj | rare | 19 | 6 |
| Classical | pron_det | all | 75 | 22 |
| Classical | uninflected | all | 50 | 15 |
| Ecclesiastical | verb | top1k | 70 | 21 |
| Ecclesiastical | verb | 1k-10k | 77 | 31 |
| Ecclesiastical | verb | rare | 28 | 0 |
| Ecclesiastical | noun | top1k | 50 | 15 |
| Ecclesiastical | noun | 1k-10k | 44 | 13 |
| Ecclesiastical | noun | rare | 31 | 10 |
| Ecclesiastical | adj | top1k | 30 | 9 |
| Ecclesiastical | adj | 1k-10k | 26 | 8 |
| Ecclesiastical | adj | rare | 19 | 6 |
| Ecclesiastical | pron_det | all | 75 | 22 |
| Ecclesiastical | uninflected | all | 50 | 15 |
| **Total** | | | 1000 | 300 |
