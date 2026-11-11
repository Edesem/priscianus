import json
import sqlite3
from pathlib import Path

import pytest

from priscianus.morphology.build_index import build_index
from priscianus.morphology.inflect import NoSuchFormError
from priscianus.verifier import SqliteIndex


def _form(form: str, *tags: str) -> dict[str, object]:
    return {"form": form, "tags": list(tags), "source": "declension"}


ROSA = {
    "word": "rosa",
    "pos": "noun",
    "forms": [_form("rosam", "accusative", "singular")],
}


def test_sqlite_index_analyses_a_form_and_knows_its_lemmas(tmp_path: Path) -> None:
    dump = tmp_path / "dump.jsonl"
    dump.write_text(json.dumps(ROSA, ensure_ascii=False) + "\n")
    db = tmp_path / "morphology.db"
    build_index(dump, db)
    index = SqliteIndex(db)

    assert [a.lemma for a in index.analyse("rosam")] == ["rosa"]
    assert index.has_lemma("rosā")
    assert not index.has_lemma("flurbus")


def test_sqlite_index_marks_analyses_found_under_a_variant_spelling(tmp_path: Path) -> None:
    dump = tmp_path / "dump.jsonl"
    entry = {"word": "affirmō", "pos": "verb", "forms": [_form("affirmat", "third-person")]}
    dump.write_text(json.dumps(entry, ensure_ascii=False) + "\n")
    db = tmp_path / "morphology.db"
    build_index(dump, db)
    index = SqliteIndex(db)

    assert [a.variant for a in index.analyse("adfirmat")] == [True]
    assert [a.variant for a in index.analyse("affirmat")] == [False]


def test_sqlite_index_inflects_a_lemma_and_raises_when_no_form_fits(tmp_path: Path) -> None:
    dump = tmp_path / "dump.jsonl"
    dump.write_text(json.dumps(ROSA, ensure_ascii=False) + "\n")
    db = tmp_path / "morphology.db"
    build_index(dump, db)
    index = SqliteIndex(db)

    assert index.inflect("rosa", {"Case": "Acc"}) == ["rosam"]
    assert index.inflect("rosa", {"Case": "Acc"}, pos="noun") == ["rosam"]
    with pytest.raises(NoSuchFormError):
        index.inflect("rosa", {"Case": "Voc"})


def test_sqlite_index_reports_the_build_hash_stored_when_it_was_built(tmp_path: Path) -> None:
    dump = tmp_path / "dump.jsonl"
    dump.write_text(json.dumps(ROSA, ensure_ascii=False) + "\n")
    db = tmp_path / "morphology.db"
    build_index(dump, db)
    con = sqlite3.connect(db)
    (stored,) = con.execute("SELECT value FROM meta WHERE key = 'build_hash'").fetchone()
    con.close()

    assert SqliteIndex(db).build_hash == stored
    assert len(stored) == 64
