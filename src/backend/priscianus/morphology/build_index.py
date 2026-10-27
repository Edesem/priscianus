"""Build the SQLite morphology index from the Wiktextract Latin dump."""

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from priscianus.morphology.normaliser import key_loose, key_macron
from priscianus.morphology.ud_features import UnknownTagError, map_tags

_SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE lemmas (
    id INTEGER PRIMARY KEY,
    lemma TEXT NOT NULL,
    lemma_display TEXT NOT NULL,
    pos TEXT NOT NULL,
    infl_class TEXT,
    freq_band TEXT,
    source TEXT NOT NULL
);
CREATE TABLE analyses (
    id INTEGER PRIMARY KEY,
    lemma_id INTEGER NOT NULL REFERENCES lemmas(id),
    form_display TEXT NOT NULL,
    key_loose TEXT NOT NULL,
    key_macron TEXT NOT NULL,
    "case" TEXT, number TEXT, gender TEXT, person TEXT, tense TEXT, aspect TEXT,
    mood TEXT, voice TEXT, verb_form TEXT, degree TEXT,
    source TEXT NOT NULL
);
CREATE INDEX analyses_key_loose ON analyses(key_loose);
CREATE INDEX analyses_lemma_id ON analyses(lemma_id);
CREATE INDEX lemmas_pos ON lemmas(pos, infl_class, freq_band);
"""

_COLUMNS: dict[str, str] = {
    "Case": "case",
    "Number": "number",
    "Gender": "gender",
    "Person": "person",
    "Tense": "tense",
    "Aspect": "aspect",
    "Mood": "mood",
    "Voice": "voice",
    "VerbForm": "verb_form",
    "Degree": "degree",
}

_ANALYSIS_COLUMNS = ["lemma_id", "form_display", "key_loose", "key_macron"]
_ANALYSIS_COLUMNS += [f'"{column}"' for column in _COLUMNS.values()] + ["source"]
_INSERT_ANALYSIS = (
    f"INSERT INTO analyses ({', '.join(_ANALYSIS_COLUMNS)})"
    f" VALUES ({', '.join('?' * len(_ANALYSIS_COLUMNS))})"
)

_SOURCE = "wiktionary"
_SCHEMA_VERSION = "1"

_LICENCE = (
    "Derived from English Wiktionary via Wiktextract (kaikki.org). "
    "Licensed CC BY-SA 4.0: attribute Wiktionary contributors, and any published copy "
    "of this database must keep the same licence."
)

_DATA_DIR = Path(__file__).resolve().parents[3] / "data"
DEFAULT_DUMP = _DATA_DIR / "raw" / "kaikki.org-dictionary-Latin.jsonl"
DEFAULT_DB = _DATA_DIR / "morphology.db"


@dataclass
class BuildReport:
    entries: int = 0
    lemmas: int = 0
    analyses: int = 0
    skipped: Counter[str] = field(default_factory=Counter)


def build_index(dump: Path, db: Path) -> BuildReport:
    report = BuildReport()
    db.unlink(missing_ok=True)
    con = sqlite3.connect(db)
    con.executescript(_SCHEMA)
    digest = hashlib.sha256(_SCHEMA_VERSION.encode())
    with dump.open("rb") as f:
        for line in f:
            digest.update(line)
            report.entries += 1
            _add_entry(con, json.loads(line), report)
    con.executemany(
        "INSERT INTO meta (key, value) VALUES (?, ?)",
        [
            ("schema_version", _SCHEMA_VERSION),
            ("dump_date", _dump_date(dump)),
            ("build_hash", digest.hexdigest()),
            ("licence", _LICENCE),
        ],
    )
    con.commit()
    con.close()
    return report


def _dump_date(dump: Path) -> str:
    sidecar = dump.with_name(dump.name + ".meta.json")
    if not sidecar.exists():
        return "unknown"
    return str(json.loads(sidecar.read_text()).get("last_modified", "unknown"))


def _readings(entry: dict[str, Any]) -> list[tuple[str, dict[str, str]]]:
    rows: list[tuple[str, dict[str, str]]] = []
    for form in entry.get("forms", []):
        rows.extend(
            (form["form"], reading) for reading in map_tags(form.get("tags", [])) if reading
        )
    return rows


def _add_entry(con: sqlite3.Connection, entry: dict[str, Any], report: BuildReport) -> None:
    try:
        rows = _readings(entry)
    except UnknownTagError as err:
        report.skipped[f"unknown tag: {', '.join(err.tags)}"] += 1
        return
    if not rows:
        report.skipped["no inflected forms"] += 1
        return
    cur = con.execute(
        "INSERT INTO lemmas (lemma, lemma_display, pos, source) VALUES (?, ?, ?, ?)",
        (key_loose(entry["word"]), entry["word"], entry["pos"], _SOURCE),
    )
    report.lemmas += 1
    for display, reading in rows:
        values = [reading.get(feature) for feature in _COLUMNS]
        con.execute(
            _INSERT_ANALYSIS,
            (cur.lastrowid, display, key_loose(display), key_macron(display), *values, _SOURCE),
        )
        report.analyses += 1


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dump", nargs="?", type=Path, default=DEFAULT_DUMP)
    parser.add_argument("db", nargs="?", type=Path, default=DEFAULT_DB)
    args = parser.parse_args(argv)

    args.db.parent.mkdir(parents=True, exist_ok=True)
    report = build_index(args.dump, args.db)
    print(f"Built {args.db}")
    print(f"entries: {report.entries}")
    print(f"lemmas: {report.lemmas}")
    print(f"analyses: {report.analyses}")
    print(f"skipped entries: {report.skipped.total()}")
    for reason, count in report.skipped.most_common():
        print(f"  {reason}: {count}")


if __name__ == "__main__":
    main()
