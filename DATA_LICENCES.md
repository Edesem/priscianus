# Data licences

Code is MIT (see `LICENSE`). Data is licensed separately.

| Source | Use | Licence | Notes |
|---|---|---|---|
| Wiktionary via Wiktextract / kaikki.org | Morphology index | CC BY-SA 4.0 (+ GFDL) | Attribute; a published built database must also be CC BY-SA. |
| Whitaker's Words (via PyWORDS) | Spot-check fixture | Free for any use (author's licence) | Only recorded analyses of 144 forms are committed, in `src/data/spot_check/whitakers.json`. |
| Perseus Latin treebank | Evals | See upstream | Downloaded by script, not committed. |
| Universal Dependencies Latin treebanks | Evals | Some CC BY-NC-SA | Non-commercial. Never commit; download by script; keep out of paid offerings. |

## Source details

### Wiktextract Latin dump

- URL: <https://kaikki.org/dictionary/Latin/kaikki.org-dictionary-Latin.jsonl>
- Fetched by `make data` (`src/data/scripts/download_wiktextract.py`) into `src/data/raw/`; never committed.
- The upstream file is regenerated periodically, so no checksum is pinned. The script checks the downloaded size against the server's `Content-Length` and that the file ends in a complete JSON line. The upstream `Last-Modified` date is saved beside the dump as `*.meta.json`.
- Attribution: data from Wiktionary (English Wiktionary contributors, CC BY-SA 4.0 and GFDL), extracted by Wiktextract and distributed via kaikki.org. Cite: Tatu Ylonen, "Wiktextract: Wiktionary as Machine-Readable Structured Data", Proceedings of LREC 2022, pp. 1317-1325.

### Universal Dependencies Latin treebanks

- Release r2.18, from the `UniversalDependencies/UD_Latin-*` repositories. The parse set uses the test splits of Perseus, PROIEL and ITTB; frequency bands use the train splits of all six (see [ADR-003](docs/adr/ADR-003.md)).
- Downloaded into `src/data/raw/`; never committed. The parse set is committed only as a manifest of sentence and word IDs (`src/data/eval_sets/`), with no treebank text.

| Treebank | Licence |
|---|---|
| Perseus | CC BY-NC-SA 2.5 |
| PROIEL | CC BY-NC-SA 4.0 |
| ITTB | CC BY-NC-SA 3.0 |
| LLCT | CC BY-SA 4.0 |
| UDante | CC BY-SA 4.0 |
| CIRCSE | CC BY-SA 4.0 |

### Built morphology database

- `make data` builds `src/data/morphology.db` from the Wiktextract dump (`priscianus.morphology.build_index`). The file is gitignored and never committed.
- It is a derived work of Wiktionary, so any published copy must be licensed CC BY-SA 4.0 and attribute Wiktionary contributors. The same note is stored in the database's `meta` table under `licence`.
