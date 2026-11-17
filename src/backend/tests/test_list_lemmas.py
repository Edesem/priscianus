import sqlite3
from pathlib import Path

from priscianus.morphology.build_index import _SCHEMA
from priscianus.morphology.lemmas import LemmaInfo, list_lemmas
from priscianus.verifier import SqliteIndex


def _make_db(tmp_path: Path, lemmas: list[dict[str, object]]) -> Path:
    """A tiny index. Each lemma gets one form unless it says `forms: 0`."""
    db = tmp_path / "morphology.db"
    con = sqlite3.connect(db)
    con.executescript(_SCHEMA)
    for i, entry in enumerate(lemmas, start=1):
        con.execute(
            "INSERT INTO lemmas (id, lemma, lemma_display, pos, infl_class, deponent,"
            " freq_band, base_lemma, source) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'test')",
            (
                i,
                entry["lemma"],
                entry["lemma"],
                entry.get("pos", "noun"),
                entry.get("infl_class"),
                entry.get("deponent", 0),
                entry.get("freq_band"),
                entry.get("base_lemma"),
            ),
        )
        if entry.get("forms", 1):
            con.execute(
                "INSERT INTO analyses (lemma_id, form_display, key_loose, key_macron, source)"
                " VALUES (?, ?, ?, ?, 'test')",
                (i, entry["lemma"], entry["lemma"], entry["lemma"]),
            )
    con.commit()
    con.close()
    return db


def _names(found: list[LemmaInfo]) -> list[str]:
    return [lemma.lemma for lemma in found]


def test_filters_only_return_lemmas_that_match_every_filter(tmp_path: Path) -> None:
    db = _make_db(
        tmp_path,
        [
            {"lemma": "rosa", "pos": "noun", "infl_class": "1", "freq_band": "A"},
            {"lemma": "dominus", "pos": "noun", "infl_class": "2", "freq_band": "A"},
            {"lemma": "amo", "pos": "verb", "infl_class": "1", "freq_band": "B"},
            {"lemma": "loquor", "pos": "verb", "infl_class": "3", "deponent": 1},
        ],
    )

    assert sorted(_names(list_lemmas(db, pos="verb"))) == ["amo", "loquor"]
    assert _names(list_lemmas(db, pos="noun", infl_class="1")) == ["rosa"]
    assert _names(list_lemmas(db, deponent=True)) == ["loquor"]
    assert _names(list_lemmas(db, deponent=False, pos="verb")) == ["amo"]
    assert sorted(_names(list_lemmas(db, freq_band="A"))) == ["dominus", "rosa"]
    assert list_lemmas(db, pos="adjective") == []


def test_result_carries_the_lemma_details_a_drill_needs(tmp_path: Path) -> None:
    db = _make_db(tmp_path, [{"lemma": "loquor", "pos": "verb", "infl_class": "3", "deponent": 1}])

    assert list_lemmas(db) == [
        LemmaInfo(
            lemma="loquor",
            lemma_display="loquor",
            pos="verb",
            infl_class="3",
            deponent=True,
            freq_band=None,
        )
    ]


def test_same_seed_gives_the_same_list_and_a_different_seed_a_different_one(
    tmp_path: Path,
) -> None:
    db = _make_db(tmp_path, [{"lemma": f"word{n:02d}"} for n in range(40)])

    first = _names(list_lemmas(db, limit=5, seed=1))
    assert first == _names(list_lemmas(db, limit=5, seed=1))
    assert first != _names(list_lemmas(db, limit=5, seed=2))


def test_limit_is_respected_and_capped_at_fifty(tmp_path: Path) -> None:
    db = _make_db(tmp_path, [{"lemma": f"word{n:03d}"} for n in range(80)])

    assert len(list_lemmas(db, limit=3)) == 3
    assert len(list_lemmas(db, limit=500)) == 50
    assert len(list_lemmas(db, limit=0)) == 0


def test_lemmas_without_forms_and_participles_are_never_returned(tmp_path: Path) -> None:
    db = _make_db(
        tmp_path,
        [
            {"lemma": "amo", "pos": "verb"},
            {"lemma": "nihil", "pos": "verb", "forms": 0},
            {"lemma": "amans", "pos": "verb", "base_lemma": "amo"},
        ],
    )

    assert _names(list_lemmas(db, pos="verb")) == ["amo"]


def test_sqlite_index_exposes_list_lemmas(tmp_path: Path) -> None:
    db = _make_db(tmp_path, [{"lemma": "rosa", "infl_class": "1"}])

    assert _names(SqliteIndex(db).list_lemmas(infl_class="1")) == ["rosa"]
