"""Tests for written feedback (ADR-005, Decision 6): a scripted API and an in-memory index."""

from pathlib import Path

from priscianus.llm.config import HAIKU
from priscianus.tutor.feedback import feedback
from priscianus.tutor.grade import grade
from priscianus.verifier.repair import ClaimState
from test_pipeline_loop import ScriptedAPI, make_client
from test_pipeline_verify import claim_json, reply
from test_tutor_drills import PERFECT_3PL
from test_tutor_grade import PERFECT_3SG, GradeIndex

INDEX = GradeIndex()


def run(api: ScriptedAPI, tmp_path: Path, answer: str = "amāvit"):  # type: ignore[no-untyped-def]
    result = grade("amo", "verb", PERFECT_3PL, answer, INDEX)
    return feedback("amo", "verb", PERFECT_3PL, answer, result, make_client(tmp_path, api), INDEX)


def test_the_model_is_told_the_grade_and_what_the_wrong_answer_is(tmp_path: Path) -> None:
    api = ScriptedAPI(reply(text="That is the singular."))

    result = run(api, tmp_path)

    prompt = api.messages.calls[0]["messages"][0]["content"]
    assert "amāvit" in prompt  # the learner's answer
    assert "amāvērunt" in prompt  # an accepted form
    assert "incorrect" in prompt.lower()
    assert "Number=Sing" in prompt  # what "amāvit" really is
    assert (result.text, result.model, result.prompt_id) == (
        "That is the singular.",
        HAIKU,
        "feedback-v1",
    )


def test_a_claim_the_index_contradicts_is_disputed_and_not_sent_back(tmp_path: Path) -> None:
    wrong = claim_json("amāvit", "amo", {**PERFECT_3SG, "Number": "Plur"})
    api = ScriptedAPI(reply(wrong, text="Amāvit is plural."))

    result = run(api, tmp_path)

    assert [c.state for c in result.claims] == [ClaimState.DISPUTED]
    assert len(api.messages.calls) == 1  # no repair call: ADR-005 sets max_repairs=0
