import json
import sqlite3
from pathlib import Path

import pytest

from priscianus.morphology.build_index import build_index, main


def _form(form: str, *tags: str, source: str = "declension") -> dict[str, object]:
    return {"form": form, "tags": list(tags), "source": source}


def _write_dump(path: Path, entries: list[dict[str, object]]) -> Path:
    path.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries))
    return path


ROSA = {
    "word": "rosa",
    "pos": "noun",
    "forms": [
        _form("rosa", "canonical", source="declension"),
        _form("no-table-tags", "table-tags"),
        _form("rosa", "nominative", "singular"),
        _form("rosārum", "genitive", "plural"),
    ],
}


def test_builds_one_analysis_row_per_inflected_form(tmp_path: Path) -> None:
    dump = _write_dump(tmp_path / "dump.jsonl", [ROSA])
    db = tmp_path / "morphology.db"

    build_index(dump, db)

    con = sqlite3.connect(db)
    rows = con.execute(
        'SELECT l.lemma, l.pos, a.form_display, a.key_loose, a.key_macron, a."case", a.number '
        "FROM analyses a JOIN lemmas l ON l.id = a.lemma_id ORDER BY a.form_display"
    ).fetchall()
    assert rows == [
        ("rosa", "noun", "rosa", "rosa", "rosa", "Nom", "Sing"),
        ("rosa", "noun", "rosārum", "rosarum", "rosārum", "Gen", "Plur"),
    ]


def test_indexes_the_loose_key_and_lemma_id(tmp_path: Path) -> None:
    dump = _write_dump(tmp_path / "dump.jsonl", [ROSA])
    db = tmp_path / "morphology.db"

    build_index(dump, db)

    con = sqlite3.connect(db)
    plan = con.execute(
        "EXPLAIN QUERY PLAN SELECT * FROM analyses WHERE key_loose = ?", ("rosa",)
    ).fetchall()
    assert any("USING INDEX" in row[-1] and "key_loose" in row[-1] for row in plan)
    indexed = {r[1] for r in con.execute("PRAGMA index_list(analyses)")}
    assert any("lemma_id" in name for name in indexed)


def test_report_counts_rows_and_skipped_entries(tmp_path: Path) -> None:
    form_of = {"word": "rosae", "pos": "noun"}
    bad_tag = {"word": "xyz", "pos": "noun", "forms": [_form("xyz", "nominative", "bogus-tag")]}
    dump = _write_dump(tmp_path / "dump.jsonl", [ROSA, form_of, bad_tag])

    report = build_index(dump, tmp_path / "morphology.db")

    assert report.entries == 3
    assert report.lemmas == 1
    assert report.analyses == 2
    assert report.skipped == {"no inflected forms": 2}
    assert report.skipped_forms == {"unknown tag: bogus-tag": 1}


def test_unknown_tag_skips_only_that_form(tmp_path: Path) -> None:
    entry = {**ROSA, "forms": [*ROSA["forms"], _form("rosīs", "ablative", "bogus-tag")]}  # type: ignore[list-item]
    db = tmp_path / "morphology.db"

    report = build_index(_write_dump(tmp_path / "dump.jsonl", [entry]), db)

    assert report.lemmas == 1
    assert report.analyses == 2
    assert report.skipped == {}
    assert report.skipped_forms == {"unknown tag: bogus-tag": 1}


def test_meta_records_schema_version_dump_date_and_build_hash(tmp_path: Path) -> None:
    dump = _write_dump(tmp_path / "dump.jsonl", [ROSA])
    (tmp_path / "dump.jsonl.meta.json").write_text(
        json.dumps({"last_modified": "Wed, 21 Oct 2026 13:51:28 GMT"})
    )
    db = tmp_path / "morphology.db"

    build_index(dump, db)

    meta = dict(sqlite3.connect(db).execute("SELECT key, value FROM meta"))
    assert meta["schema_version"] == "1"
    assert meta["dump_date"] == "Wed, 21 Oct 2026 13:51:28 GMT"
    assert len(meta["build_hash"]) == 64


def test_build_hash_is_reproducible_and_tracks_the_dump(tmp_path: Path) -> None:
    def build_hash(name: str, entries: list[dict[str, object]]) -> str:
        db = tmp_path / f"{name}.db"
        build_index(_write_dump(tmp_path / f"{name}.jsonl", entries), db)
        return str(
            sqlite3.connect(db)
            .execute("SELECT value FROM meta WHERE key='build_hash'")
            .fetchone()[0]
        )

    assert build_hash("a", [ROSA]) == build_hash("b", [ROSA])
    assert build_hash("a", [ROSA]) != build_hash("c", [ROSA, ROSA])


def test_main_builds_the_db_and_prints_row_counts_and_skips(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rosa = {**ROSA, "forms": [*ROSA["forms"], _form("rosīs", "ablative", "bogus-tag")]}  # type: ignore[list-item]
    dump = _write_dump(tmp_path / "dump.jsonl", [rosa, {"word": "rosae", "pos": "noun"}])
    db = tmp_path / "out" / "morphology.db"

    main([str(dump), str(db)])

    out = capsys.readouterr().out
    assert db.exists()
    assert "lemmas: 1" in out
    assert "analyses: 2" in out
    assert "skipped entries: 1" in out
    assert "no inflected forms: 1" in out
    assert "skipped forms: 1" in out
    assert "unknown tag: bogus-tag: 1" in out


def test_forms_without_tags_are_ignored(tmp_path: Path) -> None:
    entry = {"word": "rosa", "pos": "noun", "forms": [{"form": "rosa"}, *ROSA["forms"]]}  # type: ignore[list-item]
    dump = _write_dump(tmp_path / "dump.jsonl", [entry])

    report = build_index(dump, tmp_path / "morphology.db")

    assert report.analyses == 2


def test_meta_carries_the_cc_by_sa_licence_note(tmp_path: Path) -> None:
    db = tmp_path / "morphology.db"

    build_index(_write_dump(tmp_path / "dump.jsonl", [ROSA]), db)

    meta = dict(sqlite3.connect(db).execute("SELECT key, value FROM meta"))
    assert "CC BY-SA 4.0" in meta["licence"]
    assert "Wiktionary" in meta["licence"]


def test_aspect_keeps_imperfect_perfect_and_future_perfect_distinct(tmp_path: Path) -> None:
    amo = {
        "word": "amō",
        "pos": "verb",
        "forms": [
            _form(
                "amābat",
                "third-person",
                "singular",
                "imperfect",
                "indicative",
                "active",
                source="conjugation",
            ),
            _form(
                "amāvit",
                "third-person",
                "singular",
                "perfect",
                "indicative",
                "active",
                source="conjugation",
            ),
            _form(
                "amābit",
                "third-person",
                "singular",
                "future",
                "indicative",
                "active",
                source="conjugation",
            ),
            _form(
                "amāverit",
                "third-person",
                "singular",
                "future",
                "perfect",
                "indicative",
                "active",
                source="conjugation",
            ),
        ],
    }
    db = tmp_path / "morphology.db"

    build_index(_write_dump(tmp_path / "dump.jsonl", [amo]), db)

    rows = (
        sqlite3.connect(db)
        .execute("SELECT form_display, tense, aspect FROM analyses ORDER BY form_display")
        .fetchall()
    )
    assert rows == [
        ("amābat", "Past", "Imp"),
        ("amābit", "Fut", None),
        ("amāverit", "Fut", "Perf"),
        ("amāvit", "Past", "Perf"),
    ]


def test_only_inflection_table_forms_become_analyses(tmp_path: Path) -> None:
    thesaurus = {
        "word": "thēsaurus",
        "pos": "noun",
        "forms": [
            {"form": "thēsaurus", "tags": ["canonical", "masculine"]},
            {"form": "thēsaurī", "tags": ["genitive"]},
            {"form": "thēsaurō", "tags": ["dative", "bogus-tag"]},
            _form("thēsaurī", "genitive", "singular"),
        ],
    }
    db = tmp_path / "morphology.db"

    report = build_index(_write_dump(tmp_path / "dump.jsonl", [thesaurus]), db)

    rows = (
        sqlite3.connect(db)
        .execute('SELECT form_display, "case", number, gender FROM analyses')
        .fetchall()
    )
    assert rows == [("thēsaurī", "Gen", "Sing", None)]
    assert report.skipped_forms == {}


def _verb_with_participles() -> dict[str, object]:
    return {
        "word": "amō",
        "pos": "verb",
        "forms": [
            _form("amātus", "perfect", "passive", "participle", source="conjugation"),
            _form("amandus", "future", "passive", "participle", source="conjugation"),
        ],
    }


def _participle(word: str, *forms: tuple[str, ...]) -> dict[str, object]:
    return {
        "word": word,
        "pos": "verb",
        "senses": [{"glosses": ["loved"], "tags": ["participle"]}],
        "forms": [_form(f[0], *f[1:]) for f in forms],
    }


def test_participle_lemma_analyses_gain_tense_and_voice_from_the_verb(tmp_path: Path) -> None:
    amatus = _participle(
        "amātus",
        ("amātus", "nominative", "singular", "masculine"),
        ("amātum", "accusative", "singular", "masculine"),
    )
    db = tmp_path / "morphology.db"

    build_index(_write_dump(tmp_path / "dump.jsonl", [amatus, _verb_with_participles()]), db)

    rows = (
        sqlite3.connect(db)
        .execute(
            'SELECT l.lemma, a.form_display, a."case", a.number, a.gender, a.tense, a.aspect,'
            " a.voice, a.verb_form FROM analyses a JOIN lemmas l ON l.id = a.lemma_id"
            " WHERE l.lemma = 'amatus' ORDER BY a.form_display"
        )
        .fetchall()
    )
    assert rows == [
        ("amatus", "amātum", "Acc", "Sing", "Masc", "Past", "Perf", "Pass", "Part"),
        ("amatus", "amātus", "Nom", "Sing", "Masc", "Past", "Perf", "Pass", "Part"),
    ]


def test_gerundive_participle_is_tagged_future_passive(tmp_path: Path) -> None:
    amandus = _participle("amandus", ("amandī", "genitive", "singular", "masculine"))
    db = tmp_path / "morphology.db"

    build_index(_write_dump(tmp_path / "dump.jsonl", [_verb_with_participles(), amandus]), db)

    row = (
        sqlite3.connect(db)
        .execute(
            "SELECT tense, voice, verb_form FROM analyses a JOIN lemmas l ON l.id = a.lemma_id"
            " WHERE l.lemma = 'amandus'"
        )
        .fetchone()
    )
    assert row == ("Fut", "Pass", "Part")


def test_participle_without_a_matching_verb_form_is_left_as_is(tmp_path: Path) -> None:
    orphan = _participle("amātus", ("amātus", "nominative", "singular", "masculine"))
    db = tmp_path / "morphology.db"

    build_index(_write_dump(tmp_path / "dump.jsonl", [orphan]), db)

    row = sqlite3.connect(db).execute("SELECT tense, voice, verb_form FROM analyses").fetchone()
    assert row == (None, None, None)


def test_participle_headword_without_macrons_still_links_to_the_verb(tmp_path: Path) -> None:
    amatus = _participle("amatus", ("amātus", "nominative", "singular", "masculine"))
    db = tmp_path / "morphology.db"

    build_index(_write_dump(tmp_path / "dump.jsonl", [amatus, _verb_with_participles()]), db)

    row = (
        sqlite3.connect(db)
        .execute(
            "SELECT tense, aspect, voice, verb_form FROM analyses a"
            " JOIN lemmas l ON l.id = a.lemma_id WHERE l.lemma = 'amatus'"
        )
        .fetchone()
    )
    assert row == ("Past", "Perf", "Pass", "Part")
