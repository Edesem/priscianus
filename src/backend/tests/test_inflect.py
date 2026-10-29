import json
from pathlib import Path

import pytest

from priscianus.morphology.build_index import build_index
from priscianus.morphology.inflect import NoSuchFormError, inflect
from priscianus.morphology.lookup import lookup_form


def _form(form: str, *tags: str) -> dict[str, object]:
    return {"form": form, "tags": list(tags), "source": "declension"}


ROSA = {
    "word": "rosa",
    "pos": "noun",
    "forms": [
        _form("rosa", "nominative", "singular"),
        _form("rosae", "genitive", "singular"),
        _form("rosae", "dative", "singular"),
        _form("rosae", "nominative", "plural"),
        _form("rosam", "accusative", "singular"),
    ],
}
AMO = {
    "word": "amō",
    "pos": "verb",
    "forms": [
        _form("amō", "first-person", "singular", "present", "active", "indicative"),
        _form("amor", "first-person", "singular", "present", "passive", "indicative"),
    ],
}
AMOR = {
    "word": "amor",
    "pos": "noun",
    "forms": [_form("amor", "nominative", "singular")],
}
# Same lemma spelling as a noun and a verb, so the part of speech has to pick between them.
FORS = {"word": "fors", "pos": "noun", "forms": [_form("fors", "nominative", "singular")]}
FERO = {
    "word": "fors",
    "pos": "verb",
    "forms": [_form("ferte", "second-person", "plural", "present", "active", "imperative")],
}
# Two spellings of one slot.
NULLUS = {
    "word": "nullus",
    "pos": "adj",
    "forms": [
        _form("nullīus", "genitive", "singular"),
        _form("nullius", "genitive", "singular"),
    ],
}


# Homographs: only the length marks tell them apart.
MALUM_APPLE = {
    "word": "mālum",
    "pos": "noun",
    "forms": [_form("mālī", "genitive", "singular")],
}
MALUM_EVIL = {
    "word": "malum",
    "pos": "noun",
    "forms": [_form("malī", "genitive", "singular")],
}


@pytest.fixture
def db(tmp_path: Path) -> Path:
    entries = [ROSA, AMO, AMOR, FORS, FERO, NULLUS, MALUM_APPLE, MALUM_EVIL]
    dump = tmp_path / "dump.jsonl"
    dump.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries))
    path = tmp_path / "morphology.db"
    build_index(dump, path)
    return path


def test_rosa_dative_singular_is_rosae(db: Path) -> None:
    assert inflect("rosa", {"Case": "Dat", "Number": "Sing"}, db=db) == ["rosae"]


def test_lemma_is_normalised_like_a_lookup(db: Path) -> None:
    assert inflect("ROSA", {"Case": "Acc", "Number": "Sing"}, db=db) == ["rosam"]
    assert inflect("amō", {"Person": "1", "Voice": "Pass"}, db=db) == ["amor"]


def test_vocative_of_a_verb_raises(db: Path) -> None:
    with pytest.raises(NoSuchFormError):
        inflect("amo", {"Case": "Voc"}, db=db)


def test_unknown_lemma_raises(db: Path) -> None:
    with pytest.raises(NoSuchFormError):
        inflect("xyzzy", {"Case": "Nom"}, db=db)


def test_unfilled_cell_raises(db: Path) -> None:
    with pytest.raises(NoSuchFormError):
        inflect("rosa", {"Case": "Abl", "Number": "Sing"}, db=db)


def test_pos_picks_between_lemmas_with_the_same_spelling(db: Path) -> None:
    assert inflect("fors", {"Number": "Sing"}, pos="noun", db=db) == ["fors"]
    assert inflect("fors", {"Number": "Plur"}, pos="verb", db=db) == ["ferte"]
    with pytest.raises(NoSuchFormError):
        inflect("fors", {"Case": "Nom"}, pos="verb", db=db)


def test_every_spelling_of_a_slot_is_returned(db: Path) -> None:
    forms = inflect("nullus", {"Case": "Gen", "Number": "Sing"}, db=db)

    assert sorted(forms) == ["nullius", "nullīus"]


def test_a_lemma_only_returns_its_own_forms(db: Path) -> None:
    assert inflect("amor", {"Case": "Nom"}, db=db) == ["amor"]
    with pytest.raises(NoSuchFormError):
        inflect("amor", {"Person": "1"}, db=db)


def test_macrons_in_the_lemma_pick_between_homographs(db: Path) -> None:
    gen_sing = {"Case": "Gen", "Number": "Sing"}

    assert inflect("mālum", gen_sing, db=db) == ["mālī"]
    assert inflect("malum", gen_sing, db=db) == ["mālī", "malī"]


def test_round_trip_inflect_reproduces_every_indexed_form(db: Path) -> None:
    for entry in [ROSA, AMO, AMOR, NULLUS, MALUM_APPLE, MALUM_EVIL]:
        for table_form in entry["forms"]:
            assert isinstance(table_form, dict)
            display = table_form["form"]
            analyses = [a for a in lookup_form(display, db) if a.lemma_display == entry["word"]]
            assert analyses, display
            for analysis in analyses:
                assert display in inflect(
                    analysis.lemma_display, analysis.features, pos=analysis.pos, db=db
                )


def test_unknown_feature_name_is_a_caller_error(db: Path) -> None:
    with pytest.raises(ValueError, match="Mode"):
        inflect("rosa", {"Mode": "Ind"}, db=db)


AFFIRMO = {
    "word": "affirmō",
    "pos": "verb",
    "forms": [_form("affirmat", "third-person", "singular", "present", "active", "indicative")],
}
ADFIRMO = {
    "word": "adfirmō",
    "pos": "verb",
    "forms": [_form("adfirmat", "third-person", "singular", "present", "active", "indicative")],
}


def _db(tmp_path: Path, *entries: dict[str, object]) -> Path:
    dump = tmp_path / "dump.jsonl"
    dump.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries))
    path = tmp_path / "morphology.db"
    build_index(dump, path)
    return path


def test_inflect_falls_back_to_the_assimilated_lemma_spelling(tmp_path: Path) -> None:
    db = _db(tmp_path, AFFIRMO)

    assert inflect("adfirmo", {"Person": "3"}, db=db) == ["affirmat"]
    assert inflect("adfirmō", {"Person": "3"}, db=db) == ["affirmat"]


def test_inflect_prefers_the_exact_lemma_spelling(tmp_path: Path) -> None:
    db = _db(tmp_path, AFFIRMO, ADFIRMO)

    assert inflect("adfirmo", {"Person": "3"}, db=db) == ["adfirmat"]


def test_inflect_does_not_slide_to_a_variant_when_the_exact_lemma_lacks_the_form(
    tmp_path: Path,
) -> None:
    db = _db(tmp_path, AFFIRMO, ADFIRMO)

    with pytest.raises(NoSuchFormError):
        inflect("adfirmo", {"Person": "1"}, db=db)
