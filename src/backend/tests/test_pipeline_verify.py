"""Tests for verify-and-repair (ADR-004, Decision 4): a scripted API and an in-memory index."""

import json
from pathlib import Path
from typing import Any

from anthropic.types import Message

from priscianus.llm.config import HAIKU
from priscianus.morphology.lookup import Analysis
from priscianus.morphology.ud_features import canonical_values
from priscianus.pipeline.tools import TOOL_DEFINITIONS, execute_tool_use
from priscianus.pipeline.verify import VerifiedResult, repair_message, verify_and_repair
from priscianus.verifier.claims import Claim, ModelOutput, SchemaError, output_schema
from priscianus.verifier.classify import Verdict, classify
from priscianus.verifier.repair import ClaimState
from test_pipeline_loop import ScriptedAPI, answer, make_client, tool_use
from test_verifier_classify import FakeIndex

USER = [{"role": "user", "content": 'Parse "amat".'}]
SYSTEM = "You parse Latin."

AMAT = Analysis(
    "amo",
    "amo",
    "verb",
    "amat",
    {"Person": "3", "Number": "Sing", "Tense": "Pres", "Mood": "Ind", "VerbForm": "Fin"},
)
ROSAE_GEN = Analysis("rosa", "rosa", "noun", "rosae", {"Case": "Gen", "Number": "Sing"})
ROSAE_DAT = Analysis("rosa", "rosa", "noun", "rosae", {"Case": "Dat", "Number": "Sing"})
INDEX = FakeIndex([AMAT, ROSAE_GEN, ROSAE_DAT])

INDICATIVE = {"Person": "3", "Number": "Sing", "Tense": "Pres", "Mood": "Ind", "VerbForm": "Fin"}
SUBJUNCTIVE = {**INDICATIVE, "Mood": "Sub"}
FUTURE = {**INDICATIVE, "Tense": "Fut"}
PERFECT = {**INDICATIVE, "Tense": "Past"}


def claim_json(
    form: str, lemma: str, features: dict[str, str], upos: str = "VERB"
) -> dict[str, Any]:
    return {
        "form": form,
        "lemma": lemma,
        "upos": upos,
        "features": {name: features.get(name, "None") for name in canonical_values()},
    }


def reply(*claims: dict[str, Any], text: str = "") -> Message:
    return answer(json.dumps({"text": text, "claims": list(claims)}))


def amat(features: dict[str, str], lemma: str = "amo") -> Message:
    return reply(claim_json("amat", lemma, features))


def run(api: ScriptedAPI, tmp_path: Path, **kwargs: Any) -> VerifiedResult:
    return verify_and_repair(
        make_client(tmp_path, api),
        HAIKU,
        USER,
        TOOL_DEFINITIONS,
        lambda block: execute_tool_use(block, INDEX),
        INDEX,
        system=SYSTEM,
        output_schema=output_schema(),
        **kwargs,
    )


def only(result: VerifiedResult) -> Any:
    assert len(result.claims) == 1
    return result.claims[0]


def test_a_claim_fixed_on_the_first_retry(tmp_path: Path) -> None:
    api = ScriptedAPI(amat(SUBJUNCTIVE), amat(INDICATIVE))
    result = run(api, tmp_path)

    assert only(result).classification.verdict is Verdict.VERIFIED
    assert only(result).state is ClaimState.VERIFIED
    assert len(api.messages.calls) == 2
    assert [a.attempt for a in result.attempts] == [0, 1]
    assert [a.stop_reason for a in result.attempts] == [None, "cleared"]


def test_a_claim_fixed_on_the_second_retry(tmp_path: Path) -> None:
    api = ScriptedAPI(amat(SUBJUNCTIVE), amat(FUTURE), amat(INDICATIVE))
    result = run(api, tmp_path)

    assert only(result).state is ClaimState.VERIFIED
    assert len(api.messages.calls) == 3
    assert [a.stop_reason for a in result.attempts] == [None, None, "cleared"]


def test_a_claim_never_fixed_is_flagged_after_two_retries_not_dropped(tmp_path: Path) -> None:
    api = ScriptedAPI(amat(SUBJUNCTIVE), amat(FUTURE), amat(PERFECT))
    result = run(api, tmp_path)

    assert len(api.messages.calls) == 3  # one first pass and two repairs, never a third
    assert only(result).state is ClaimState.DISPUTED
    assert only(result).claim.features["Tense"] == "Past"
    assert result.attempts[-1].stop_reason == "limit"


def test_an_ambiguous_claim_triggers_no_repair(tmp_path: Path) -> None:
    api = ScriptedAPI(reply(claim_json("rosae", "rosa", {"Case": "Gen", "Number": "Sing"}, "NOUN")))
    result = run(api, tmp_path)

    assert len(api.messages.calls) == 1
    assert only(result).state is ClaimState.AMBIGUOUS
    assert only(result).classification.others == (ROSAE_DAT,)
    assert len(result.attempts) == 1


def test_the_claims_before_repair_are_kept_next_to_the_final_ones(tmp_path: Path) -> None:
    api = ScriptedAPI(amat(SUBJUNCTIVE), amat(INDICATIVE))
    result = run(api, tmp_path)

    before = result.pre_repair_claims
    assert [c.claim.features["Mood"] for c in before] == ["Sub"]
    assert [c.state for c in before] == [ClaimState.DISPUTED]
    assert only(result).claim.features["Mood"] == "Ind"


def test_every_attempt_keeps_its_message_response_and_verdicts(tmp_path: Path) -> None:
    api = ScriptedAPI(amat(SUBJUNCTIVE), amat(INDICATIVE))
    first, second = run(api, tmp_path).attempts

    assert first.message is None
    assert second.message is not None and '"amat"' in second.message
    assert first.loop.response.text != second.loop.response.text
    assert [c.classification.verdict for c in first.claims] == [Verdict.CONTRADICTED]
    assert [c.classification.verdict for c in second.claims] == [Verdict.VERIFIED]


def test_the_repair_turn_sends_the_index_readings_after_the_models_own_answer(
    tmp_path: Path,
) -> None:
    api = ScriptedAPI(amat(SUBJUNCTIVE), amat(INDICATIVE))
    run(api, tmp_path)

    messages = api.messages.calls[1]["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant", "user"]
    assert '"Mood": "Sub"' in messages[1]["content"][0]["text"]
    assert "Mood=Ind" in messages[2]["content"]


def test_the_repair_turn_can_still_call_tools(tmp_path: Path) -> None:
    api = ScriptedAPI(
        amat(SUBJUNCTIVE),
        tool_use(("t1", "lookup_form", {"form": "amat"})),
        amat(INDICATIVE),
    )
    result = run(api, tmp_path)

    assert only(result).state is ClaimState.VERIFIED
    assert [t.name for t in result.attempts[1].loop.tool_calls] == ["lookup_form"]
    assert len(api.messages.calls) == 3


def test_a_repair_turn_gets_one_tool_round_then_must_answer(tmp_path: Path) -> None:
    lookup = ("t", "lookup_form", {"form": "amat"})
    api = ScriptedAPI(
        amat(SUBJUNCTIVE), tool_use(lookup), tool_use(("u", *lookup[1:])), amat(INDICATIVE)
    )
    result = run(api, tmp_path)

    assert result.attempts[1].loop.tool_limit_hit is True
    assert api.messages.calls[3]["tool_choice"] == {"type": "none"}


def test_a_restated_claim_stops_repair_early(tmp_path: Path) -> None:
    api = ScriptedAPI(amat(SUBJUNCTIVE), amat(SUBJUNCTIVE))
    result = run(api, tmp_path)

    assert len(api.messages.calls) == 2
    assert only(result).state is ClaimState.DISPUTED
    assert result.attempts[-1].stop_reason == "restated"


def test_a_repair_that_fails_the_schema_leaves_the_previous_claims_standing(
    tmp_path: Path,
) -> None:
    api = ScriptedAPI(amat(SUBJUNCTIVE), answer("not json"))
    result = run(api, tmp_path)

    assert only(result).claim.features["Mood"] == "Sub"
    assert only(result).state is ClaimState.DISPUTED
    last = result.attempts[-1]
    assert isinstance(last.loop.output, SchemaError)
    assert last.stop_reason == "schema_failure"
    assert last.claims == ()


def test_a_first_pass_that_fails_the_schema_has_no_claims_and_no_repair(tmp_path: Path) -> None:
    api = ScriptedAPI(answer("not json"))
    result = run(api, tmp_path)

    assert len(api.messages.calls) == 1
    assert result.claims == ()
    assert isinstance(result.output, SchemaError)


def test_the_final_output_is_the_last_valid_answer(tmp_path: Path) -> None:
    api = ScriptedAPI(
        reply(claim_json("amat", "amo", SUBJUNCTIVE), text="first"),
        reply(claim_json("amat", "amo", INDICATIVE), text="kept it right"),
    )
    result = run(api, tmp_path)

    assert isinstance(result.output, ModelOutput)
    assert result.output.text == "kept it right"


def test_only_the_claims_that_need_repair_are_listed_in_the_message() -> None:
    bad = Claim("amat", "amo", "VERB", SUBJUNCTIVE)
    classified = classify(bad, INDEX)
    message = repair_message([(bad, classified)])

    assert 'about "amat"' in message
    assert "lemma amo" in message
    assert "Mood=Sub" in message
    assert "The index has the lemma, but not this reading of the form." in message
    assert '"lemma":"amo"' in message and "Mood=Ind" in message
    assert "gold" not in message.lower()


def test_the_message_for_an_unknown_lemma_says_the_index_does_not_hold_it() -> None:
    bad = Claim("amat", "amare", "VERB", INDICATIVE)
    message = repair_message([(bad, classify(bad, INDEX))])

    assert 'The index does not hold the lemma "amare".' in message
    assert "has the lemma, but not" not in message
