"""Tests for drills (ADR-005, Decision 3): a scripted API and an in-memory index."""

import json
from pathlib import Path
from typing import Any

import pytest

from priscianus.llm.config import HAIKU
from priscianus.morphology.inflect import NoSuchFormError
from priscianus.morphology.lemmas import LemmaInfo
from priscianus.morphology.lookup import Analysis
from priscianus.morphology.ud_features import canonical_values
from priscianus.tutor.drills import DrillInputError, DrillSet, make_drills
from test_pipeline_loop import ScriptedAPI, answer, make_client, tool_use

PERFECT_3PL = {
    "Person": "3",
    "Number": "Plur",
    "Tense": "Past",
    "Aspect": "Perf",
    "Mood": "Ind",
    "Voice": "Act",
    "VerbForm": "Fin",
}
PRESENT_3SG = {
    "Person": "3",
    "Number": "Sing",
    "Tense": "Pres",
    "Mood": "Ind",
    "Voice": "Act",
    "VerbForm": "Fin",
}


class DrillIndex:
    """An in-memory index with a table of forms and a list of lemmas. It records `seed`."""

    def __init__(self) -> None:
        self.forms = {
            ("amo", "verb", tuple(sorted(PERFECT_3PL.items()))): [
                "amāvērunt",
                "amārunt",
                "amāvēre",
            ],
            ("rex", "noun", (("Case", "Nom"), ("Number", "Plur"))): ["rēgēs"],
            ("amo", "verb", tuple(sorted(PRESENT_3SG.items()))): ["amat"],
            # A vague item: the index has forms, but they are a whole row of the paradigm.
            ("amo", "verb", (("Aspect", "Perf"), ("Tense", "Past"))): ["amāvī", "amāvistī"],
        }
        self.seeds: list[int] = []

    def analyse(self, form: str) -> list[Analysis]:
        return []

    def has_lemma(self, lemma: str) -> bool:
        return lemma in {"amo", "rex"}

    def inflect(self, lemma: str, features: dict[str, str], pos: str | None = None) -> list[str]:
        key = (lemma, pos, tuple(sorted(features.items())))
        if key not in self.forms:
            raise NoSuchFormError(f"No form of {lemma!r} with features {features}")
        return self.forms[key]

    def list_lemmas(self, *, limit: int = 20, seed: int = 0, **filters: Any) -> list[LemmaInfo]:
        self.seeds.append(seed)
        return [LemmaInfo("amo", "amō", "verb", "1", False, None)]


def item(lemma: str, pos: str, features: dict[str, str]) -> dict[str, Any]:
    return {"lemma": lemma, "pos": pos, "features": features}


def drills_reply(*items: dict[str, Any], message: str = "") -> Any:
    return answer(json.dumps({"message": message, "items": list(items)}))


def run(
    api: ScriptedAPI,
    tmp_path: Path,
    request: str = "perfect tense of amo",
    count: int = 10,
    index: DrillIndex | None = None,
) -> DrillSet:
    return make_drills(request, make_client(tmp_path, api), index or DrillIndex(), count)


def test_every_accepted_form_comes_from_the_index_not_the_model(tmp_path: Path) -> None:
    api = ScriptedAPI(drills_reply(item("amo", "verb", PERFECT_3PL)))

    result = run(api, tmp_path, count=1)

    assert len(result.items) == 1
    assert result.items[0].accepted == ("amāvērunt", "amārunt", "amāvēre")
    assert result.shortfall == 0
    assert (result.model, result.prompt_id) == (HAIKU, "drills-v1")
    assert api.messages.calls[0]["model"] == HAIKU


def test_none_means_the_feature_does_not_apply_and_is_left_out(tmp_path: Path) -> None:
    every_feature = {name: "None" for name in canonical_values()}
    nominative_plural = {**every_feature, "Case": "Nom", "Number": "Plur"}
    api = ScriptedAPI(drills_reply(item("rex", "noun", nominative_plural)))

    result = run(api, tmp_path, count=1)

    assert result.items[0].features == {"Case": "Nom", "Number": "Plur"}
    assert result.items[0].accepted == ("rēgēs",)


def test_the_prompt_text_is_written_by_code_from_lemma_and_features(tmp_path: Path) -> None:
    api = ScriptedAPI(drills_reply(item("amo", "verb", PERFECT_3PL)))

    result = run(api, tmp_path, count=1)

    assert result.items[0].prompt == "Give the 3rd person plural perfect active indicative of amo."


def test_an_item_with_no_index_form_is_never_returned(tmp_path: Path) -> None:
    made_up = item("amo", "verb", {**PERFECT_3PL, "Number": "Sing"})  # not in the index
    unknown = item("blorpus", "noun", {"Case": "Nom", "Number": "Plur"})
    good = item("rex", "noun", {"Case": "Nom", "Number": "Plur"})
    api = ScriptedAPI(drills_reply(made_up, unknown, good))

    result = run(api, tmp_path, count=3)

    assert [i.lemma for i in result.items] == ["rex"]
    assert result.shortfall == 2


def test_an_item_that_does_not_pick_out_one_form_is_never_returned(tmp_path: Path) -> None:
    vague = item("amo", "verb", {"Tense": "Past", "Aspect": "Perf"})  # no person, number or mood
    good = item("rex", "noun", {"Case": "Nom", "Number": "Plur"})
    api = ScriptedAPI(drills_reply(vague, good))

    result = run(api, tmp_path, count=2)

    assert [i.lemma for i in result.items] == ["rex"]


def test_duplicates_are_dropped_and_extra_items_are_trimmed_to_count(tmp_path: Path) -> None:
    amo = item("amo", "verb", PERFECT_3PL)
    rex = item("rex", "noun", {"Case": "Nom", "Number": "Plur"})
    api = ScriptedAPI(drills_reply(amo, amo, rex))

    assert [i.lemma for i in run(api, tmp_path, count=2).items] == ["amo", "rex"]


def test_an_impossible_request_returns_no_items_and_a_message(tmp_path: Path) -> None:
    api = ScriptedAPI(drills_reply(message="A noun has no person, so there is no 1st person."))

    result = run(api, tmp_path, "1st person of rex")

    assert result.items == ()
    assert result.message == "A noun has no person, so there is no 1st person."


def test_when_every_item_is_dropped_the_code_writes_the_message(tmp_path: Path) -> None:
    api = ScriptedAPI(drills_reply(item("blorpus", "noun", {"Case": "Nom"})))

    result = run(api, tmp_path)

    assert result.items == ()
    assert result.message  # code wrote it: the model's own message was empty


def test_the_present_is_still_found_when_the_model_adds_the_imperfect_aspect(
    tmp_path: Path,
) -> None:
    slip = {**PRESENT_3SG, "Aspect": "Imp"}  # Haiku does this often; the index has no such form
    api = ScriptedAPI(drills_reply(item("amo", "verb", slip)))

    result = run(api, tmp_path, count=1)

    assert result.items[0].accepted == ("amat",)
    assert result.items[0].prompt.startswith("Give the 3rd person singular present active")


def test_the_model_s_message_is_not_used_when_it_gave_items_that_were_all_dropped(
    tmp_path: Path,
) -> None:
    bogus = item("blorpus", "noun", {"Case": "Nom", "Number": "Plur"})
    api = ScriptedAPI(drills_reply(bogus, message="I have given you six good items."))

    result = run(api, tmp_path)

    assert result.items == ()
    assert result.message and "six good items" not in result.message


def test_a_noun_s_gender_is_left_out_so_the_prompt_cannot_state_a_false_one(
    tmp_path: Path,
) -> None:
    feminine = {"Case": "Nom", "Number": "Plur", "Gender": "Fem"}
    api = ScriptedAPI(drills_reply(item("rex", "noun", feminine)))

    result = run(api, tmp_path, count=1)

    assert result.items[0].features == {"Case": "Nom", "Number": "Plur"}
    assert result.items[0].prompt == "Give the nominative plural of rex."


def test_the_model_can_list_lemmas_and_the_same_request_gives_the_same_seed(
    tmp_path: Path,
) -> None:
    def scripted() -> ScriptedAPI:
        call = ("t1", "list_lemmas", {"pos": "verb", "infl_class": "1"})
        return ScriptedAPI(tool_use(call), drills_reply(item("amo", "verb", PERFECT_3PL)))

    index = DrillIndex()
    api = scripted()
    result = run(api, tmp_path, index=index)
    again = tmp_path / "again"
    again.mkdir()
    run(scripted(), again, index=index)  # a second client, so nothing is cached

    tool_result = api.messages.calls[1]["messages"][-1]["content"][0]["content"]
    assert "amo" in tool_result
    assert len(index.seeds) == 2 and index.seeds[0] == index.seeds[1]
    assert len(result.items) == 1


BAD_REQUESTS = [("", 5), ("x" * 201, 5), ("verbs", 0), ("verbs", 11)]


@pytest.mark.parametrize("request_text, count", BAD_REQUESTS)
def test_a_bad_request_is_refused_before_any_api_call(
    tmp_path: Path, request_text: str, count: int
) -> None:
    api = ScriptedAPI()

    with pytest.raises(DrillInputError):
        run(api, tmp_path, request_text, count)

    assert api.messages.calls == []
