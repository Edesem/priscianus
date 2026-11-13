"""Verified mode of the parse run (#76): tools, the verifier and the repair loop."""

import json
import sqlite3

import pytest
from anthropic.types import TextBlock, ToolUseBlock
from priscianus.morphology.lookup import Analysis

from evals.gold import parse_conllu
from evals.parse_set import Item
from evals.raw_prompt import ALLOWED_FEATURES
from evals.report import repair_summary, residual_error
from evals.run import run_parse
from evals.store import EvalStore
from evals.tools_prompt import VERIFIED_PROMPT_ID
from tests.test_run import ANSWERS, CONLLU, MODEL, client_for
from tests.test_run_tools import _message

BUILD = "build-1"
NOM_SG_FEM = {"Case": "Nom", "Number": "Sing", "Gender": "Fem"}


class RepairIndex:
    """Knows *omnis* and *divisa* (so a wrong answer about them is CONTRADICTED and has
    readings to send back) and *est*. Knows nothing about *Gallia* or *in*."""

    _READINGS = {
        "est": ("sum", "verb", ANSWERS["est"][2]),
        "omnis": ("omnis", "adj", NOM_SG_FEM),
        "divisa": (
            "divido",
            "verb",
            {**NOM_SG_FEM, "Tense": "Past", "VerbForm": "Part", "Voice": "Pass"},
        ),
    }

    def analyse(self, form):
        if form not in self._READINGS:
            return []
        lemma, pos, features = self._READINGS[form]
        return [Analysis(lemma, lemma, pos, form, features)]

    def has_lemma(self, lemma):
        return lemma in {"sum", "omnis", "diuido"}  # lemma keys write v as u


# What the fake model says on each turn for a form: the first answer, then one per repair message.
SCRIPT = {
    "Gallia": [("Gallia", "NOUN", NOM_SG_FEM)],
    "est": [ANSWERS["est"]],
    "in": [ANSWERS["in"]],
    # Wrong case first, then right after the index's readings are sent back: repaired.
    "omnis": [
        ("omnis", "ADJ", {**NOM_SG_FEM, "Case": "Acc"}),
        ("omnis", "ADJ", NOM_SG_FEM),
    ],
    # Wrong, and wrong in a new way on both repair turns: still wrong after 2 retries.
    "divisa": [
        ("divido", "VERB", {**NOM_SG_FEM, "Case": "Acc", "VerbForm": "Part", "Voice": "Pass"}),
        ("divido", "VERB", {**NOM_SG_FEM, "Case": "Gen", "VerbForm": "Part", "Voice": "Pass"}),
        ("divido", "VERB", {**NOM_SG_FEM, "Case": "Dat", "VerbForm": "Part", "Voice": "Pass"}),
    ],
}


class VerifiedMessages:
    """A fake model that looks the target up, answers, and answers again on each repair turn."""

    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        messages = kwargs["messages"]
        form = messages[0]["content"].split('Word to analyse: "')[1].split('"')[0]
        if len(messages) == 1:
            block = ToolUseBlock(type="tool_use", id="t1", name="lookup_form", input={"form": form})
            return _message([block], "tool_use")
        # Messages: question, lookup, its result, answer, then (repair message, answer) pairs.
        turn = max(0, (len(messages) - 3) // 2)
        lemma, upos, given = SCRIPT[form][min(turn, len(SCRIPT[form]) - 1)]
        features = {name: given.get(name, "None") for name in ALLOWED_FEATURES}
        claim = {"form": form, "lemma": lemma, "upos": upos, "features": features}
        text = json.dumps({"text": "", "claims": [claim]})
        return _message([TextBlock(type="text", text=text)], "end_turn")


@pytest.fixture
def tokens():
    return parse_conllu(CONLLU, treebank="perseus")


@pytest.fixture
def items(tokens):
    return [Item("dev", t, "Classical", "perseus", "verb", "top1k") for t in tokens]


@pytest.fixture
def store(tmp_path):
    return EvalStore(tmp_path / "evals.db")


@pytest.fixture
def api():
    return type("Api", (), {"messages": VerifiedMessages()})()


@pytest.fixture
def run_id(tmp_path, items, tokens, api, store):
    summary = run_parse(
        items,
        tokens,
        client_for(tmp_path, api),
        RepairIndex(),
        store,
        model=MODEL,
        manifest_version="v1",
        split="dev",
        git_commit="abc",
        mode="verified",
        index_build_hash=BUILD,
    )
    assert summary.answered == 5
    assert summary.status == "complete"
    return summary.run_id


def stored(store, run_id, form):
    return store.read_response(
        run_id, f"perseus/s1/{ {'Gallia': 1, 'est': 2, 'omnis': 3, 'divisa': 4, 'in': 5}[form] }"
    )


def test_a_five_item_set_runs_end_to_end_under_the_verified_prompt(store, run_id):
    assert store.run_info(run_id).prompt_id == VERIFIED_PROMPT_ID
    assert store.run_info(run_id).mode == "verified"
    conn = sqlite3.connect(store.path)
    # Only the two wrong answers were sent back: one repair turn for *omnis*, two for *divisa*.
    assert conn.execute("SELECT COUNT(*) FROM repair_attempts").fetchone() == (3,)
    # Every API call is stored: 2 per item, plus 1 per repair turn.
    assert conn.execute("SELECT COUNT(*) FROM costs").fetchone() == (13,)


def test_a_repaired_item_keeps_the_claim_before_repair_and_the_final_one(store, run_id):
    response = stored(store, run_id, "omnis")
    first, final = response.claims
    assert (first.attempt, first.is_final, first.verdict) == (0, False, "contradicted")
    assert first.claim["features"]["Case"] == "Acc"
    assert first.score["exact_match"] is False
    assert (final.attempt, final.is_final, final.verdict) == (1, True, "verified")
    assert final.score["exact_match"] is True
    assert response.final_state == "verified"
    assert [r.stop_reason for r in response.repair_attempts] == ["cleared"]
    assert "does not confirm" in response.repair_attempts[0].message_text


def test_an_item_still_wrong_after_two_retries_is_flagged_not_dropped(store, run_id):
    response = stored(store, run_id, "divisa")
    assert [c.attempt for c in response.claims] == [0, 1, 2]
    final = response.claims[-1]
    assert final.is_final
    assert final.claim["features"]["Case"] == "Dat"
    assert (final.verdict, final.score["exact_match"]) == ("contradicted", False)
    assert response.final_state == "disputed"
    assert [r.stop_reason for r in response.repair_attempts] == [None, "limit"]


def test_an_item_that_needs_no_repair_has_one_claim_and_no_repair_attempts(store, run_id):
    response = stored(store, run_id, "est")
    assert [c.attempt for c in response.claims] == [0]
    assert response.repair_attempts == []
    assert response.final_state == "verified"


def test_repair_success_and_harm_compare_the_first_pass_with_the_final_claim(store, run_id):
    rows = store.run_rows(run_id)
    summary = repair_summary(rows, store.first_passes(run_id))
    # *omnis* went from wrong to right; *divisa* entered repair and stayed wrong.
    assert (summary.items, summary.entered, summary.success, summary.harm) == (5, 2, 1, 0)
    # Exact match is of the final claims: Gallia, est, omnis, in are right.
    assert sum(r.score["exact_match"] for r in rows) == 4


def test_residual_error_counts_a_flagged_wrong_answer_as_caught_not_missing(store, run_id):
    cells = residual_error(store.run_rows(run_id))
    # *divisa* is wrong and disputed. *Gallia* and *in* are right but unchecked (not in the
    # index). *est* and *omnis* are right and verified. Nothing wrong reaches the learner unflagged.
    assert (cells.false_assurance, cells.unchecked_error) == (0, 0)
    assert (cells.caught_error, cells.false_alarm) == (1, 0)
    assert (cells.correct, cells.correct_unchecked) == (2, 2)
