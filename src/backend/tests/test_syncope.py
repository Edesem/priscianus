import json
from pathlib import Path

import pytest

from priscianus.morphology.build_index import build_index
from priscianus.morphology.lookup import lookup_form
from priscianus.morphology.syncope import syncopate


@pytest.mark.parametrize(
    ("perfect", "syncopated"),
    [
        ("nūntiāvērunt", "nūntiārunt"),
        ("nuntiaverint", "nuntiarint"),
        ("custōdīvistis", "custōdīstis"),
        ("amāvistī", "amāstī"),
        ("amāvissem", "amāssem"),
        ("audīvērunt", "audiērunt"),
    ],
)
def test_syncopates_a_perfect_stem_before_its_ending(perfect: str, syncopated: str) -> None:
    assert syncopate(perfect) == syncopated


@pytest.mark.parametrize("form", ["amāvit", "amāvī", "rosa", "amāvērat"])
def test_leaves_forms_without_a_syncopable_ending_alone(form: str) -> None:
    assert syncopate(form) is None


def test_indexes_a_syncopated_perfect_as_an_analysis_of_its_verb(tmp_path: Path) -> None:
    entry = {
        "word": "custōdiō",
        "pos": "verb",
        "forms": [
            {
                "form": "custōdīvistis",
                "tags": ["second-person", "plural", "perfect", "active", "indicative"],
                "source": "conjugation",
            }
        ],
    }
    dump = tmp_path / "dump.jsonl"
    dump.write_text(json.dumps(entry, ensure_ascii=False) + "\n")
    db = tmp_path / "morphology.db"
    build_index(dump, db)

    analyses = lookup_form("custodistis", db)

    assert [(a.lemma, a.form) for a in analyses] == [("custodio", "custōdīstis")]
    assert analyses[0].features == {
        "Person": "2",
        "Number": "Plur",
        "Tense": "Past",
        "Aspect": "Perf",
        "Mood": "Ind",
        "Voice": "Act",
        "VerbForm": "Fin",
    }


def test_does_not_repeat_a_syncopated_form_that_wiktionary_already_lists(tmp_path: Path) -> None:
    tags = ["second-person", "plural", "perfect", "active", "indicative"]
    entry = {
        "word": "custōdiō",
        "pos": "verb",
        "forms": [
            {"form": "custōdīvistis", "tags": tags, "source": "conjugation"},
            {"form": "custōdīstis", "tags": tags, "source": "conjugation"},
        ],
    }
    dump = tmp_path / "dump.jsonl"
    dump.write_text(json.dumps(entry, ensure_ascii=False) + "\n")
    db = tmp_path / "morphology.db"

    report = build_index(dump, db)

    assert report.syncopated == 0
    assert len(lookup_form("custodistis", db)) == 1
