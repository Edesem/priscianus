import json
from pathlib import Path

import pytest

from priscianus.morphology.build_index import build_index
from priscianus.morphology.lookup import Analysis, lookup_form
from priscianus.morphology.normaliser import key_loose


def _form(form: str, *tags: str) -> dict[str, object]:
    return {"form": form, "tags": list(tags), "source": "declension"}


AMOR_NOUN = {
    "word": "amor",
    "pos": "noun",
    "forms": [_form("amor", "nominative", "singular"), _form("amōrem", "accusative", "singular")],
}
AMO_VERB = {
    "word": "amō",
    "pos": "verb",
    "forms": [
        _form("amor", "first-person", "singular", "present", "passive", "indicative"),
        _form("amō", "first-person", "singular", "present", "active", "indicative"),
    ],
}
ROSA = {
    "word": "rosa",
    "pos": "noun",
    "forms": [
        _form("rosae", "genitive", "singular"),
        _form("rosae", "dative", "singular"),
        _form("rosae", "nominative", "plural"),
        _form("rosam", "accusative", "singular"),
    ],
}
SUM = {
    "word": "sum",
    "pos": "verb",
    "forms": [_form("est", "third-person", "singular", "present", "active", "indicative")],
}
VITA = {
    "word": "vita",
    "pos": "noun",
    "forms": [_form("vīta", "nominative", "singular")],
}
EDO = {
    "word": "edō",
    "pos": "verb",
    "forms": [_form("est", "third-person", "singular", "present", "active", "indicative")],
}


LOQUOR = {
    "word": "loquor",
    "pos": "verb",
    "head_templates": [
        {"expansion": "loquor (perfect active locūtus sum); third conjugation, deponent"}
    ],
    "forms": [_form("loquitur", "third-person", "singular", "present", "active", "indicative")],
}


@pytest.fixture
def db(tmp_path: Path) -> Path:
    entries = [AMOR_NOUN, AMO_VERB, ROSA, SUM, EDO, VITA, LOQUOR]
    dump = tmp_path / "dump.jsonl"
    dump.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries))
    path = tmp_path / "morphology.db"
    build_index(dump, path)
    return path


def test_amor_is_both_a_noun_and_a_passive_verb(db: Path) -> None:
    analyses = lookup_form("amor", db)

    assert sorted((a.lemma, a.pos) for a in analyses) == [("amo", "verb"), ("amor", "noun")]
    noun = next(a for a in analyses if a.pos == "noun")
    verb = next(a for a in analyses if a.pos == "verb")
    assert noun.features == {"Case": "Nom", "Number": "Sing"}
    assert verb.features == {
        "Person": "1",
        "Number": "Sing",
        "Tense": "Pres",
        "Mood": "Ind",
        "VerbForm": "Fin",
        "Voice": "Pass",
    }
    assert verb.lemma_display == "amō"
    assert isinstance(noun, Analysis)


@pytest.mark.parametrize("spelling", ["AMOR", "  amor\n", "ămor", "amōr"])
def test_normalises_case_whitespace_and_length_marks(db: Path, spelling: str) -> None:
    assert lookup_form(spelling, db) == lookup_form("amor", db)
    assert lookup_form(spelling, db) != []


@pytest.mark.parametrize("spelling", ["vita", "uita", "VĪTA"])
def test_normalises_consonantal_v_and_j(db: Path, spelling: str) -> None:
    assert [a.lemma_display for a in lookup_form(spelling, db)] == ["vita"]


@pytest.mark.parametrize("unknown", ["xyzzy", "", "   ", "amorx"])
def test_unknown_forms_give_an_empty_list(db: Path, unknown: str) -> None:
    assert lookup_form(unknown, db) == []


def test_rosae_has_one_analysis_per_case_reading(db: Path) -> None:
    analyses = lookup_form("rosae", db)

    assert {(a.lemma, tuple(sorted(a.features.items()))) for a in analyses} == {
        ("rosa", (("Case", "Gen"), ("Number", "Sing"))),
        ("rosa", (("Case", "Dat"), ("Number", "Sing"))),
        ("rosa", (("Case", "Nom"), ("Number", "Plur"))),
    }


def test_est_is_both_sum_and_edo(db: Path) -> None:
    analyses = lookup_form("est", db)

    assert sorted(a.lemma for a in analyses) == ["edo", "sum"]
    assert all(a.features["Person"] == "3" and a.features["Tense"] == "Pres" for a in analyses)


def test_analysis_of_a_deponent_lemma_is_flagged(db: Path) -> None:
    [analysis] = lookup_form("loquitur", db)

    assert analysis.deponent is True
    assert analysis.features["Voice"] == "Act"


def test_analysis_of_an_ordinary_verb_is_not_flagged(db: Path) -> None:
    analyses = lookup_form("amo", db)

    assert [a.deponent for a in analyses] == [False]


PAVENS = {
    "word": "pavēns",
    "pos": "verb",
    "senses": [
        {
            "glosses": ["fearing"],
            "tags": ["active", "form-of", "participle", "present"],
            "form_of": [{"word": "paveō"}],
        }
    ],
    "forms": [_form("paventes", "accusative", "plural", "masculine")],
}
MAIOR = {
    "word": "maior",
    "pos": "adj",
    "senses": [
        {
            "glosses": ["greater"],
            "tags": ["comparative", "form-of"],
            "form_of": [{"word": "magnus"}],
        }
    ],
    "forms": [_form("maiores", "nominative", "plural", "feminine")],
}


def test_participle_and_comparative_analyses_name_their_base_lemma(tmp_path: Path) -> None:
    db = tmp_path / "morphology.db"
    dump = tmp_path / "dump.jsonl"
    dump.write_text(
        "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in [PAVENS, MAIOR, ROSA])
    )
    build_index(dump, db)

    [paventes] = lookup_form("paventes", db)
    [maiores] = lookup_form("maiores", db)
    [rosae, *_] = lookup_form("rosae", db)

    assert paventes.base_lemma == key_loose("paveo")
    assert maiores.base_lemma == "magnus"
    assert rosae.base_lemma is None
