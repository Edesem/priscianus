import json
from pathlib import Path

import pytest

from priscianus.morphology.__main__ import main
from priscianus.morphology.build_index import build_index

AMOR_NOUN = {
    "word": "amor",
    "pos": "noun",
    "forms": [{"form": "amor", "tags": ["nominative", "singular"], "source": "declension"}],
}
AMO_VERB = {
    "word": "amō",
    "pos": "verb",
    "forms": [
        {
            "form": "amor",
            "tags": ["first-person", "singular", "present", "passive", "indicative"],
            "source": "declension",
        }
    ],
}


@pytest.fixture
def db(tmp_path: Path) -> Path:
    dump = tmp_path / "dump.jsonl"
    dump.write_text(
        "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in [AMOR_NOUN, AMO_VERB])
    )
    path = tmp_path / "morphology.db"
    build_index(dump, path)
    return path


def test_parse_prints_every_analysis_of_an_ambiguous_form(
    db: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["parse", "amor"], db=db)

    out = capsys.readouterr().out
    assert code == 0
    assert "amor" in out
    assert "2 analyses" in out
    assert "amor: form of amor (noun): Case=Nom, Number=Sing" in out
    verb = "Number=Sing, Person=1, Tense=Pres, Mood=Ind, Voice=Pass, VerbForm=Fin"
    assert f"amor: form of amō (verb): {verb}" in out


def test_parse_says_so_for_an_unknown_word(db: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["parse", "xyzzy"], db=db)

    captured = capsys.readouterr()
    assert code == 1
    assert "No analyses found for 'xyzzy'" in captured.err
    assert captured.out == ""


def test_parse_reports_a_missing_index_instead_of_a_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["parse", "amor"], db=tmp_path / "missing.db")

    assert code == 2
    assert "make data" in capsys.readouterr().err
