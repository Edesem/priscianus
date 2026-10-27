"""Build the SQLite morphology index from the Wiktextract Latin dump."""

import json
import sqlite3
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from priscianus.morphology.normaliser import key_loose, key_macron
from priscianus.morphology.ud_features import UnknownTagError, map_tags

_SCHEMA = """
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
    "case" TEXT, number TEXT, gender TEXT, person TEXT, tense TEXT,
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
    "Mood": "mood",
    "Voice": "voice",
    "VerbForm": "verb_form",
    "Degree": "degree",
}

_SOURCE = "wiktionary"


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
    with dump.open(encoding="utf-8") as f:
        for line in f:
            report.entries += 1
            _add_entry(con, json.loads(line), report)
    con.commit()
    con.close()
    return report


def _readings(entry: dict[str, Any]) -> list[tuple[str, dict[str, str]]]:
    rows: list[tuple[str, dict[str, str]]] = []
    for form in entry.get("forms", []):
        rows.extend((form["form"], reading) for reading in map_tags(form["tags"]) if reading)
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
            'INSERT INTO analyses (lemma_id, form_display, key_loose, key_macron, "case", number,'
            " gender, person, tense, mood, voice, verb_form, degree, source)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (cur.lastrowid, display, key_loose(display), key_macron(display), *values, _SOURCE),
        )
        report.analyses += 1
