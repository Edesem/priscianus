import json
from pathlib import Path

import pytest

from priscianus.morphology.build_index import build_index
from priscianus.morphology.lookup import Analysis, lookup_form


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
EDO = {
    "word": "edō",
    "pos": "verb",
    "forms": [_form("est", "third-person", "singular", "present", "active", "indicative")],
}


@pytest.fixture
def db(tmp_path: Path) -> Path:
    entries = [AMOR_NOUN, AMO_VERB, ROSA, SUM, EDO]
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
