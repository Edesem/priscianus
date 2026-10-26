# Data licences

Code is MIT (see `LICENSE`). Data is licensed separately.

| Source | Use | Licence | Notes |
|---|---|---|---|
| Wiktionary via Wiktextract / kaikki.org | Morphology index | CC BY-SA 4.0 (+ GFDL) | Attribute; a published built database must also be CC BY-SA. |
| Perseus Latin treebank | Evals | See upstream | Downloaded by script, not committed. |
| Universal Dependencies Latin treebanks | Evals | Some CC BY-NC-SA | Non-commercial. Never commit; download by script; keep out of paid offerings. |

## Source details

### Wiktextract Latin dump

- URL: <https://kaikki.org/dictionary/Latin/kaikki.org-dictionary-Latin.jsonl>
- Fetched by `make data` (`src/data/scripts/download_wiktextract.py`) into `src/data/raw/`; never committed.
- The upstream file is regenerated periodically, so no checksum is pinned. The script checks the downloaded size against the server's `Content-Length` and that the file ends in a complete JSON line. The upstream `Last-Modified` date is saved beside the dump as `*.meta.json`.
- Attribution: data from Wiktionary (English Wiktionary contributors, CC BY-SA 4.0 and GFDL), extracted by Wiktextract and distributed via kaikki.org. Cite: Tatu Ylonen, "Wiktextract: Wiktionary as Machine-Readable Structured Data", Proceedings of LREC 2022, pp. 1317-1325.
