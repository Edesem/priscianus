"""Tests for the tool definitions and executor (ADR-004, Decision 2), on an in-memory index."""

import json
from typing import Any

from priscianus.morphology.inflect import NoSuchFormError
from priscianus.morphology.lookup import Analysis
from priscianus.morphology.normaliser import key_loose
from priscianus.pipeline.tools import TOOL_DEFINITIONS, execute_tool_use


class FakeIndex:
    """An in-memory `MorphologyIndex`: no database, no `make data`."""

    def __init__(self, analyses: list[Analysis]) -> None:
        self._analyses = analyses

    def analyse(self, form: str) -> list[Analysis]:
        return [a for a in self._analyses if key_loose(a.form) == key_loose(form)]

    def has_lemma(self, lemma: str) -> bool:
        return any(key_loose(a.lemma) == key_loose(lemma) for a in self._analyses)

    def inflect(self, lemma: str, features: dict[str, str], pos: str | None = None) -> list[str]:
        forms = [
            a.form
            for a in self._analyses
            if key_loose(a.lemma) == key_loose(lemma)
            and (pos is None or a.pos == pos)
            and all(a.features.get(k) == v for k, v in features.items())
        ]
        if not forms:
            raise NoSuchFormError(f"No form of {lemma!r} with features {features}")
        return list(dict.fromkeys(forms))


def reading(
    form: str,
    lemma: str,
    features: dict[str, str],
    *,
    pos: str = "noun",
    lemma_display: str | None = None,
    deponent: bool = False,
    base_lemma: str | None = None,
    variant: bool = False,
) -> Analysis:
    return Analysis(
        lemma=lemma,
        lemma_display=lemma_display or lemma,
        pos=pos,
        form=form,
        features=features,
        deponent=deponent,
        base_lemma=base_lemma,
        variant=variant,
    )


LOQUITUR = reading(
    "loquitur",
    "loquor",
    {
        "Mood": "Ind",
        "Number": "Sing",
        "Person": "3",
        "Tense": "Pres",
        "VerbForm": "Fin",
        "Voice": "Act",
    },
    pos="verb",
    deponent=True,
)


def use(name: str, arguments: dict[str, Any], tool_use_id: str = "toolu_1") -> dict[str, Any]:
    return {"type": "tool_use", "id": tool_use_id, "name": name, "input": arguments}


def run(index: FakeIndex, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return execute_tool_use(use(name, arguments), index)


def content(result: dict[str, Any]) -> dict[str, Any]:
    decoded: dict[str, Any] = json.loads(result["content"])
    return decoded


def test_definitions_give_each_tool_a_name_description_and_input_schema() -> None:
    by_name = {t["name"]: t for t in TOOL_DEFINITIONS}

    assert set(by_name) == {"lookup_form", "inflect"}
    assert by_name["lookup_form"]["input_schema"]["required"] == ["form"]
    assert by_name["inflect"]["input_schema"]["required"] == ["lemma", "features"]
    assert all(t["input_schema"]["type"] == "object" for t in TOOL_DEFINITIONS)
    assert all(t["input_schema"]["additionalProperties"] is False for t in TOOL_DEFINITIONS)


def test_definitions_tell_the_model_what_an_empty_result_does_not_mean() -> None:
    text = " ".join(t["description"] for t in TOOL_DEFINITIONS)

    assert "does not mean" in text and "wrong" in text  # an error is not a verdict on the form
    assert "gender" in text  # a missing feature means the index does not record it
    assert "deponent" in text and "Voice=Act" in text


def test_lookup_form_returns_a_tool_result_with_compact_sorted_json() -> None:
    result = run(FakeIndex([LOQUITUR]), "lookup_form", {"form": "loquitur"})

    assert result["type"] == "tool_result"
    assert result["tool_use_id"] == "toolu_1"
    assert "is_error" not in result
    assert result["content"] == (
        '{"form":"loquitur","readings":[{"deponent":true,'
        '"features":"Mood=Ind|Number=Sing|Person=3|Tense=Pres|VerbForm=Fin|Voice=Act",'
        '"form":"loquitur","lemma":"loquor","pos":"verb"}],"total":1,"truncated":false}'
    )


def test_lookup_form_shows_the_display_lemma_and_the_links_only_when_set() -> None:
    amandus = reading(
        "amandus",
        "amandus",
        {
            "Case": "Nom",
            "Gender": "Masc",
            "Number": "Sing",
            "Tense": "Fut",
            "VerbForm": "Part",
            "Voice": "Pass",
        },
        pos="verb",
        lemma_display="amandus",
        base_lemma="amo",
    )
    malum = reading(
        "malum", "malum", {"Case": "Nom", "Number": "Sing"}, lemma_display="mālum", variant=True
    )

    gerundive = content(run(FakeIndex([amandus]), "lookup_form", {"form": "amandus"}))["readings"][
        0
    ]
    variant = content(run(FakeIndex([malum]), "lookup_form", {"form": "malum"}))["readings"][0]

    assert gerundive["base_lemma"] == "amo"
    assert "VerbForm=Gdv" in gerundive["features"]
    assert "Voice" not in gerundive["features"]
    assert "deponent" not in gerundive and "variant" not in gerundive
    assert variant["lemma"] == "mālum"
    assert variant["variant"] is True and "base_lemma" not in variant


def test_lookup_form_merges_readings_the_way_the_verifier_does() -> None:
    first = reading("rosae", "rosa", {"Case": "Gen", "Number": "Sing"})
    again = reading("rosae", "rosa", {"Case": "Gen", "Number": "Sing"})
    dative = reading("rosae", "rosa", {"Case": "Dat", "Number": "Sing"})

    body = content(run(FakeIndex([first, again, dative]), "lookup_form", {"form": "rosae"}))

    assert body["total"] == 2
    assert [r["features"] for r in body["readings"]] == [
        "Case=Gen|Number=Sing",
        "Case=Dat|Number=Sing",
    ]


def test_lookup_form_shows_at_most_fifty_readings_and_reports_the_real_total() -> None:
    many = [reading("se", f"lemma{i}", {"Case": "Acc"}) for i in range(60)]

    body = content(run(FakeIndex(many), "lookup_form", {"form": "se"}))

    assert len(body["readings"]) == 50
    assert body["total"] == 60
    assert body["truncated"] is True


def assert_error(result: dict[str, Any], code: str) -> dict[str, Any]:
    assert result["type"] == "tool_result"
    assert result["tool_use_id"] == "toolu_1"
    assert result["is_error"] is True
    body = content(result)
    assert set(body) == {"error", "message"}
    assert body["error"] == code
    assert body["message"]
    return body


def test_lookup_form_of_a_form_the_index_lacks_is_an_error_that_is_not_a_verdict() -> None:
    body = assert_error(
        run(FakeIndex([LOQUITUR]), "lookup_form", {"form": "flurbus"}), "unknown_form"
    )

    assert "does not hold" in body["message"]
    assert "not mean" in body["message"]


def test_lookup_form_rejects_arguments_that_fail_the_schema() -> None:
    index = FakeIndex([LOQUITUR])

    for bad in ({}, {"form": 3}, {"form": "loquitur", "extra": 1}, {"form": "-"}, {"form": "  "}):
        assert_error(run(index, "lookup_form", bad), "invalid_input")


def test_an_unknown_tool_is_an_error_that_names_the_available_tools() -> None:
    body = assert_error(run(FakeIndex([]), "list_lemmas", {}), "unknown_tool")

    assert "lookup_form" in body["message"] and "inflect" in body["message"]


def test_arguments_that_are_not_an_object_are_invalid_input() -> None:
    block = {"type": "tool_use", "id": "toolu_1", "name": "lookup_form", "input": "loquitur"}

    assert_error(execute_tool_use(block, FakeIndex([])), "invalid_input")
