"""Build the SQLite morphology index from the Wiktextract Latin dump."""

import json
import sqlite3
from pathlib import Path

from priscianus.morphology.normaliser import key_loose, key_macron
from priscianus.morphology.ud_features import map_tags

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
"""

_COLUMNS = {
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


def build_index(dump: Path, db: Path) -> None:
    db.unlink(missing_ok=True)
    con = sqlite3.connect(db)
    con.executescript(_SCHEMA)
    with dump.open(encoding="utf-8") as f:
        for line in f:
            _add_entry(con, json.loads(line))
    con.commit()
    con.close()


def _add_entry(con: sqlite3.Connection, entry: dict[str, object]) -> None:
    rows: list[tuple[str, dict[str, str]]] = []
    for form in entry.get("forms", []):  # type: ignore[attr-defined]
        for reading in map_tags(form["tags"]):
            if reading:
                rows.append((form["form"], reading))
    if not rows:
        return
    cur = con.execute(
        "INSERT INTO lemmas (lemma, lemma_display, pos, source) VALUES (?, ?, ?, ?)",
        (key_loose(str(entry["word"])), entry["word"], entry["pos"], _SOURCE),
    )
    for display, reading in rows:
        values = {col: reading.get(feat) for feat, col in _COLUMNS.items()}
        con.execute(
            'INSERT INTO analyses (lemma_id, form_display, key_loose, key_macron, "case", number,'
            " gender, person, tense, mood, voice, verb_form, degree, source)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                cur.lastrowid,
                display,
                key_loose(display),
                key_macron(display),
                *values.values(),
                _SOURCE,
            ),
        )
