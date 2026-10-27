import pytest

from priscianus.morphology.whitakers import whitakers_to_ud


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
