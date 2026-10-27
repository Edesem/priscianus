import json
from pathlib import Path

import pytest

from priscianus.morphology.build_index import build_index
from priscianus.morphology.whitakers import compare, whitakers_to_ud


def test_noun_ending_maps_case_and_number_and_drops_unspecified_gender():
    assert whitakers_to_ud({"case": "GEN", "number": "P", "gender": "C"}) == {
        "Case": "Gen",
        "Number": "Plur",
    }


def test_adjective_ending_keeps_gender_and_degree():
    infl = {"case": "NOM", "number": "S", "gender": "N", "comparison": "COMP"}
    assert whitakers_to_ud(infl) == {
        "Case": "Nom",
        "Number": "Sing",
        "Gender": "Neut",
        "Degree": "Cmp",
    }


def test_imperfect_indicative_active_is_past_imperfective_finite():
    infl = {"tense": "IMPF", "voice": "ACTIVE", "mood": "IND", "person": "3", "number": "S"}
    assert whitakers_to_ud(infl) == {
        "Tense": "Past",
        "Aspect": "Imp",
        "Voice": "Act",
        "Mood": "Ind",
        "VerbForm": "Fin",
        "Person": "3",
        "Number": "Sing",
    }


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("PRES", {"Tense": "Pres"}),
        ("PERF", {"Tense": "Past", "Aspect": "Perf"}),
        ("FUT", {"Tense": "Fut"}),
        ("FUTP", {"Tense": "Fut", "Aspect": "Perf"}),
        ("PLUP", {"Tense": "Pqp"}),
    ],
)
def test_tense_codes(code: str, expected: dict[str, str]):
    assert whitakers_to_ud({"tense": code}) == expected


def test_infinitive_has_verb_form_and_no_mood():
    infl = {"tense": "PRES", "voice": "PASSIVE", "mood": "INF"}
    assert whitakers_to_ud(infl) == {"Tense": "Pres", "Voice": "Pass", "VerbForm": "Inf"}


def test_participle_mood_becomes_verb_form():
    infl = {"case": "ACC", "number": "S", "gender": "M", "tense": "PERF", "voice": "PASSIVE"}
    assert whitakers_to_ud(infl, verb_form="Part") == {
        "Case": "Acc",
        "Number": "Sing",
        "Gender": "Masc",
        "Tense": "Past",
        "Aspect": "Perf",
        "Voice": "Pass",
        "VerbForm": "Part",
    }


def test_placeholder_codes_are_dropped():
    assert whitakers_to_ud({"case": "X", "number": "X", "gender": "X", "person": "0"}) == {}


def test_unknown_code_raises():
    with pytest.raises(ValueError, match="TENSE"):
        whitakers_to_ud({"tense": "NOPE"})


def _form(form: str, *tags: str) -> dict[str, object]:
    return {"form": form, "tags": list(tags), "source": "declension"}


@pytest.fixture
def db(tmp_path: Path) -> Path:
    entries = [
        {
            "word": "rosa",
            "pos": "noun",
            "forms": [
                _form("rosae", "genitive", "singular"),
                _form("rosae", "nominative", "plural"),
            ],
        }
    ]
    dump = tmp_path / "dump.jsonl"
    dump.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries))
    path = tmp_path / "morphology.db"
    build_index(dump, path)
    return path


def test_compare_agrees_when_every_whitakers_analysis_is_in_the_index(db: Path):
    expected = [{"Case": "Gen", "Number": "Sing"}, {"Case": "Nom", "Number": "Plur"}]
    result = compare("rosae", expected, db)
    assert result.status == "agree"
    assert result.unmatched == []


def test_compare_ignores_extra_features_the_index_has(db: Path):
    assert compare("rosae", [{"Case": "Gen"}], db).status == "agree"


def test_compare_reports_a_form_the_index_lacks(db: Path):
    result = compare("rosarum", [{"Case": "Gen", "Number": "Plur"}], db)
    assert result.status == "missing"
    assert result.found == []


def test_compare_reports_analyses_the_index_does_not_have(db: Path):
    expected = [{"Case": "Gen", "Number": "Sing"}, {"Case": "Dat", "Number": "Sing"}]
    result = compare("rosae", expected, db)
    assert result.status == "differ"
    assert result.unmatched == [{"Case": "Dat", "Number": "Sing"}]
