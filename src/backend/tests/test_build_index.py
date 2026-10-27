import json
import sqlite3
from pathlib import Path

from priscianus.morphology.build_index import build_index


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
