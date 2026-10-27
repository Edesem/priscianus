import json
from pathlib import Path

import pytest

from priscianus.morphology.build_index import build_index
from priscianus.morphology.whitakers import compare, spot_check, whitakers_to_ud


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


def _write_fixture(path: Path, entries: list[dict[str, object]]) -> Path:
    path.write_text(json.dumps(entries))
    return path


def test_spot_check_maps_codes_and_compares_each_word(db: Path, tmp_path: Path):
    fixture = _write_fixture(
        tmp_path / "whitakers.json",
        [
            {
                "word": "rosae",
                "analyses": [
                    {"pos": "N", "verb_form": None, "infl": {"case": "GEN", "number": "S"}},
                    {"pos": "N", "verb_form": None, "infl": {"case": "DAT", "number": "S"}},
                ],
            },
            {
                "word": "rosarum",
                "analyses": [{"pos": "N", "verb_form": None, "infl": {"case": "GEN"}}],
            },
        ],
    )
    results = spot_check(fixture, db)
    assert [(r.word, r.status) for r in results] == [("rosae", "differ"), ("rosarum", "missing")]
    assert results[0].unmatched == [{"Case": "Dat", "Number": "Sing"}]


def test_spot_check_skips_words_whitakers_could_not_analyse(db: Path, tmp_path: Path):
    fixture = _write_fixture(tmp_path / "whitakers.json", [{"word": "est", "analyses": []}])
    assert spot_check(fixture, db) == []


def test_spot_check_passes_verb_form_of_participles_and_supines(db: Path, tmp_path: Path):
    fixture = _write_fixture(
        tmp_path / "whitakers.json",
        [{"word": "rosae", "analyses": [{"pos": "VPAR", "verb_form": "Part", "infl": {}}]}],
    )
    (result,) = spot_check(fixture, db)
    assert result.unmatched == [{"VerbForm": "Part"}]


def test_spot_check_does_not_require_noun_gender_or_positive_degree(db: Path, tmp_path: Path):
    fixture = _write_fixture(
        tmp_path / "whitakers.json",
        [
            {
                "word": "rosae",
                "analyses": [
                    {"pos": "N", "verb_form": None, "infl": {"case": "GEN", "gender": "F"}},
                    {"pos": "ADJ", "verb_form": None, "infl": {"case": "GEN", "comparison": "POS"}},
                ],
            }
        ],
    )
    (result,) = spot_check(fixture, db)
    assert result.status == "agree"


def _verb_db(tmp_path: Path, lemma: str, form: str) -> Path:
    entry = {
        "word": lemma,
        "pos": "verb",
        "forms": [
            {
                "form": form,
                "tags": ["active", "indicative", "present", "singular", "third-person"],
                "source": "conjugation",
            }
        ],
    }
    dump = tmp_path / "verb.jsonl"
    dump.write_text(json.dumps(entry, ensure_ascii=False) + "\n")
    path = tmp_path / "verb.db"
    build_index(dump, path)
    return path


def _passive_verb_fixture(tmp_path: Path, word: str, entry: str) -> Path:
    infl = {"number": "S", "person": "3", "tense": "PRES", "voice": "PASSIVE", "mood": "IND"}
    analysis = {"pos": "V", "verb_form": None, "entry": entry, "infl": infl}
    return _write_fixture(tmp_path / "whitakers.json", [{"word": word, "analyses": [analysis]}])


def test_spot_check_accepts_active_for_whitakers_passive_on_a_deponent(tmp_path: Path):
    db = _verb_db(tmp_path, "loquor", "loquitur")
    fixture = _passive_verb_fixture(tmp_path, "loquitur", "loquor, loqui, locutus sum")
    (result,) = spot_check(fixture, db)
    assert result.status == "agree"


def test_spot_check_still_requires_passive_voice_on_a_regular_verb(tmp_path: Path):
    db = _verb_db(tmp_path, "amo", "amatur")
    fixture = _passive_verb_fixture(tmp_path, "amatur", "amo, amare, amavi, amatus")
    (result,) = spot_check(fixture, db)
    assert result.status == "differ"
