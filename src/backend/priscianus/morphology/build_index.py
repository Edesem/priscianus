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
from priscianus.morphology.syncope import syncopate
from priscianus.morphology.ud_features import UnknownTagError, map_tags

_SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE lemmas (
    id INTEGER PRIMARY KEY,
    lemma TEXT NOT NULL,
    lemma_display TEXT NOT NULL,
    pos TEXT NOT NULL,
    infl_class TEXT,
    deponent INTEGER NOT NULL DEFAULT 0,
    freq_band TEXT,
    base_lemma TEXT,
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

# Forms from inflection tables carry full feature sets. Headword-line forms (no source)
# carry only a tag or two, such as the genitive or the lemma's gender, so they are not analyses.
_TABLE_SOURCES = frozenset({"declension", "conjugation", "inflection"})
_SCHEMA_VERSION = "3"

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
    deponents: int = 0
    syncopated: int = 0
    skipped: Counter[str] = field(default_factory=Counter)
    skipped_forms: Counter[str] = field(default_factory=Counter)


def build_index(dump: Path, db: Path) -> BuildReport:
    report = BuildReport()
    db.unlink(missing_ok=True)
    con = sqlite3.connect(db)
    con.executescript(_SCHEMA)
    digest = hashlib.sha256(_SCHEMA_VERSION.encode())
    participles: dict[int, str] = {}
    with dump.open("rb") as f:
        for line in f:
            digest.update(line)
            report.entries += 1
            entry = json.loads(line)
            lemma_id = _add_entry(con, entry, report)
            if lemma_id is not None and _is_participle(entry):
                participles[lemma_id] = key_loose(entry["word"])
    _merge_participle_features(con, participles)
    report.syncopated = _add_syncopated_perfects(con)
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


_SYNCOPE_SOURCE = "syncopation"


def _add_syncopated_perfects(con: sqlite3.Connection) -> int:
    """Add the syncopated spelling of each active finite perfect that has one.

    Wiktionary tables list *nuntiāvērunt* but not *nuntiārunt*. The new analysis has the
    same lemma and features as the full form, and its own source so that it can be told apart.
    """
    columns = ", ".join(f'"{column}"' for column in _COLUMNS.values())
    rows = con.execute(
        f"SELECT lemma_id, form_display, {columns} FROM analyses"
        " WHERE tense = 'Past' AND aspect = 'Perf' AND voice = 'Act' AND verb_form = 'Fin'"
    ).fetchall()
    existing = {(lemma_id, key_loose(form), *features) for lemma_id, form, *features in rows}
    added = 0
    for lemma_id, form, *features in rows:
        short = syncopate(form)
        if short is None or (lemma_id, key_loose(short), *features) in existing:
            continue
        con.execute(
            _INSERT_ANALYSIS,
            (lemma_id, short, key_loose(short), key_macron(short), *features, _SYNCOPE_SOURCE),
        )
        added += 1
    return added


def _dump_date(dump: Path) -> str:
    sidecar = dump.with_name(dump.name + ".meta.json")
    if not sidecar.exists():
        return "unknown"
    return str(json.loads(sidecar.read_text()).get("last_modified", "unknown"))


def _readings(entry: dict[str, Any], report: BuildReport) -> list[tuple[str, dict[str, str]]]:
    rows: list[tuple[str, dict[str, str]]] = []
    for form in entry.get("forms", []):
        if form.get("source") not in _TABLE_SOURCES:
            continue
        try:
            readings = map_tags(form.get("tags", []))
        except UnknownTagError as err:
            report.skipped_forms[f"unknown tag: {', '.join(err.tags)}"] += 1
            continue
        rows.extend((form["form"], reading) for reading in readings if reading)
    return rows


def _is_participle(entry: dict[str, Any]) -> bool:
    return entry["pos"] == "verb" and any(
        "participle" in sense.get("tags", []) for sense in entry.get("senses", [])
    )


def _merge_participle_features(con: sqlite3.Connection, participles: dict[int, str]) -> None:
    """Copy Tense/Aspect/Voice/VerbForm from a verb's participle row onto the participle lemma.

    Wiktionary puts tense and voice on the verb's row (no case) and case, number and gender
    on the participle's own lemma (no tense), so neither alone is a full analysis. The two
    are linked by the participle's citation form. An ambiguous link is left unmerged.
    """
    by_citation: dict[str, set[tuple[str | None, ...]]] = {}
    for key, *features in con.execute(
        "SELECT key_loose, tense, aspect, voice, verb_form FROM analyses"
        " WHERE verb_form = 'Part' AND \"case\" IS NULL"
    ):
        by_citation.setdefault(key, set()).add(tuple(features))
    for lemma_id, citation in participles.items():
        found = by_citation.get(citation, set())
        if len(found) != 1:
            continue
        con.execute(
            "UPDATE analyses SET tense = ?, aspect = ?, voice = ?, verb_form = ?"
            " WHERE lemma_id = ? AND verb_form IS NULL",
            (*next(iter(found)), lemma_id),
        )


# Sense tags of the forms whose lemma is another lemma's form: a participle, gerund or supine
# is a form of its verb, and a comparative or superlative is a form of its positive.
_BASE_LEMMA_TAGS = frozenset({"participle", "gerund", "supine", "comparative", "superlative"})


def _base_lemma(entry: dict[str, Any]) -> str | None:
    """The key of the lemma that this entry is a form of, if Wiktionary names exactly one.

    Wiktionary links a participle, gerund, supine or comparative to its base in `form_of`.
    Senses that name different bases are ambiguous and get none.
    """
    senses = entry.get("senses", [])
    if not any(_BASE_LEMMA_TAGS & set(sense.get("tags", [])) for sense in senses):
        return None
    bases = {
        key_loose(link["word"])
        for sense in senses
        if _BASE_LEMMA_TAGS & set(sense.get("tags", []))
        for link in sense.get("form_of", [])
    }
    return bases.pop() if len(bases) == 1 else None


def _is_deponent(entry: dict[str, Any]) -> bool:
    """Whether Wiktionary's headword line calls a verb deponent or semi-deponent.

    The line reads "...; third conjugation, deponent" or "...; second conjugation, optionally
    semi-deponent". A `deponent` tag on a single sense is not enough: it marks a deponent use
    of a verb that is active elsewhere (*manducō*). Semi-deponents are flagged with the
    deponents, as ADR-002 and ADR-003 do not compare their voice either.
    """
    return entry["pos"] == "verb" and any(
        "deponent" in template.get("expansion", "") for template in entry.get("head_templates", [])
    )


def _entry_degree(entry: dict[str, Any]) -> str | None:
    """Degree of a comparative or superlative lemma, from its sense tags.

    Wiktionary lists these as their own lemmas, so their inflection tables carry no degree.
    An entry tagged as both is ambiguous and gets none.
    """
    tags = {tag for sense in entry.get("senses", []) for tag in sense.get("tags", [])}
    degrees = {"comparative": "Cmp", "superlative": "Sup"}
    found = {degree for tag, degree in degrees.items() if tag in tags}
    return found.pop() if len(found) == 1 else None


def _add_entry(con: sqlite3.Connection, entry: dict[str, Any], report: BuildReport) -> int | None:
    rows = _readings(entry, report)
    if not rows:
        report.skipped["no inflected forms"] += 1
        return None
    deponent = int(_is_deponent(entry))
    cur = con.execute(
        "INSERT INTO lemmas (lemma, lemma_display, pos, deponent, base_lemma, source)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (
            key_loose(entry["word"]),
            entry["word"],
            entry["pos"],
            deponent,
            _base_lemma(entry),
            _SOURCE,
        ),
    )
    report.lemmas += 1
    report.deponents += deponent
    degree = _entry_degree(entry)
    for display, reading in rows:
        reading = {"Degree": degree, **reading} if degree else reading
        values = [reading.get(feature) for feature in _COLUMNS]
        con.execute(
            _INSERT_ANALYSIS,
            (cur.lastrowid, display, key_loose(display), key_macron(display), *values, _SOURCE),
        )
        report.analyses += 1
    return cur.lastrowid


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
    print(f"deponent lemmas: {report.deponents}")
    print(f"syncopated perfects: {report.syncopated}")
    print(f"skipped entries: {report.skipped.total()}")
    for reason, count in report.skipped.most_common():
        print(f"  {reason}: {count}")
    print(f"skipped forms: {report.skipped_forms.total()}")
    for reason, count in report.skipped_forms.most_common():
        print(f"  {reason}: {count}")


if __name__ == "__main__":
    main()
