"""Tests for explain (ADR-005, Decision 2): a scripted API and an in-memory index."""

import json
from pathlib import Path
from typing import Any

import pytest

from priscianus.llm.config import HAIKU, SONNET
from priscianus.morphology.lookup import Analysis
from priscianus.tutor.explain import ExplainInputError, ExplainResult, explain
from priscianus.verifier.repair import ClaimState
from test_pipeline_loop import ScriptedAPI, answer, make_client, tool_use
from test_pipeline_verify import claim_json, reply
from test_verifier_classify import FakeIndex

ARMA = Analysis("arma", "arma", "noun", "arma", {"Case": "Nom", "Number": "Plur"})
CANO = Analysis(
    "cano",
    "cano",
    "verb",
    "cano",
    {"Person": "1", "Number": "Sing", "Tense": "Pres", "Mood": "Ind", "VerbForm": "Fin"},
)
VIR = Analysis("vir", "vir", "noun", "virum", {"Case": "Acc", "Number": "Sing"})
INDEX = FakeIndex([ARMA, CANO, VIR])

ARMA_CLAIM = claim_json("arma", "arma", {"Case": "Nom", "Number": "Plur"}, "NOUN")
VIRUM_CLAIM = claim_json("virum", "vir", {"Case": "Acc", "Number": "Sing"}, "NOUN")
CANO_CLAIM = claim_json(
    "cano",
    "cano",
    {"Person": "1", "Number": "Sing", "Tense": "Pres", "Mood": "Ind", "VerbForm": "Fin"},
)


def run(api: ScriptedAPI, tmp_path: Path, text: str) -> ExplainResult:
    return explain(text, make_client(tmp_path, api), INDEX)


def test_a_three_word_sentence_gets_three_claims_with_states(tmp_path: Path) -> None:
    api = ScriptedAPI(reply(ARMA_CLAIM, VIRUM_CLAIM, CANO_CLAIM, text="I sing of arms and a man."))

    result = run(api, tmp_path, "Arma virumque cano")

    assert [w.token for w in result.words] == ["Arma", "virumque", "cano"]
    assert [w.claim.state for w in result.words if w.claim] == [ClaimState.VERIFIED] * 3
    assert result.text == "I sing of arms and a man."
    assert (result.model, result.prompt_id, result.dropped_claims) == (SONNET, "explain-v1", 0)


def test_a_single_word_uses_the_cheaper_model(tmp_path: Path) -> None:
    api = ScriptedAPI(reply(CANO_CLAIM))

    result = run(api, tmp_path, "cano")

    assert result.model == HAIKU
    assert api.messages.calls[0]["model"] == HAIKU


def test_a_contradicted_claim_is_flagged_disputed_and_not_sent_back(tmp_path: Path) -> None:
    wrong = claim_json("arma", "arma", {"Case": "Gen", "Number": "Sing"}, "NOUN")
    api = ScriptedAPI(reply(wrong))

    result = run(api, tmp_path, "arma")

    assert result.words[0].claim is not None
    assert result.words[0].claim.state is ClaimState.DISPUTED
    assert len(api.messages.calls) == 1  # no repair call: ADR-005 sets max_repairs=0


def test_a_non_word_ends_unverifiable(tmp_path: Path) -> None:
    api = ScriptedAPI(reply(claim_json("xyzzy", "xyzzy", {}, "X")))

    result = run(api, tmp_path, "xyzzy")

    assert result.words[0].claim is not None
    assert result.words[0].claim.state is ClaimState.UNVERIFIABLE


@pytest.mark.parametrize("text", ["word " * 26, "a" * 301])
def test_overlong_input_is_rejected_before_any_api_call(tmp_path: Path, text: str) -> None:
    api = ScriptedAPI()

    with pytest.raises(ExplainInputError):
        run(api, tmp_path, text)

    assert api.messages.calls == []


def test_a_long_sentence_can_look_up_every_word_in_one_round(tmp_path: Path) -> None:
    lookups: list[tuple[str, str, dict[str, Any]]] = [
        (f"t{i}", "lookup_form", {"form": "arma"}) for i in range(6)
    ]
    api = ScriptedAPI(tool_use(*lookups), answer(json.dumps({"text": "", "claims": []})))

    run(api, tmp_path, "arma arma arma arma arma arma")

    results = api.messages.calls[1]["messages"][-1]["content"]
    assert [r.get("is_error", False) for r in results] == [False] * 6
