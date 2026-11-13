"""Tools mode of the parse run (#75): the model can call the index; nothing verifies it."""

import json
import sqlite3

import pytest
from anthropic.types import Message, TextBlock, ToolUseBlock
from anthropic.types import Usage as AnthropicUsage

from evals.gold import parse_conllu
from evals.parse_set import Item
from evals.raw_prompt import ALLOWED_FEATURES
from evals.run import run_parse
from evals.store import EvalStore
from evals.tools_prompt import PROMPT_ID, SYSTEM_PROMPT
from tests.test_run import ANSWERS, CONLLU, MODEL, FakeIndex, client_for

BUILD = "build-1"


def _message(content, stop_reason):
    return Message(
        id="m",
        type="message",
        role="assistant",
        model=MODEL,
        content=content,
        stop_reason=stop_reason,
        stop_sequence=None,
        usage=AnthropicUsage(input_tokens=1000, output_tokens=100),
    )


class ToolCallingMessages:
    """A fake model that looks the target up first, then answers as `test_run.ANSWERS` says.

    `answer_for` can replace the final answer for a form, to make it a bad one.
    """

    def __init__(self, answer_for=None):
        self.calls = []
        self.answer_for = answer_for or {}

    def create(self, **kwargs):
        self.calls.append(kwargs)
        first = kwargs["messages"][0]["content"]
        form = first.split('Word to analyse: "')[1].split('"')[0]
        if len(kwargs["messages"]) == 1:
            block = ToolUseBlock(type="tool_use", id="t1", name="lookup_form", input={"form": form})
            return _message([block], "tool_use")
        if form in self.answer_for:
            return _message([TextBlock(type="text", text=self.answer_for[form])], "end_turn")
        if form not in ANSWERS:
            return _message([TextBlock(type="text", text="not json")], "end_turn")
        lemma, upos, given = ANSWERS[form]
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
    return type("Api", (), {"messages": ToolCallingMessages()})()


def go(tmp_path, items, tokens, api, store, **kwargs):
    return run_parse(
        items,
        tokens,
        client_for(tmp_path, api),
        FakeIndex(),
        store,
        model=MODEL,
        manifest_version="v1",
        split="dev",
        git_commit="abc",
        mode="tools",
        index_build_hash=BUILD,
        **kwargs,
    )


def query(store, sql):
    return sqlite3.connect(store.path).execute(sql).fetchall()


def test_a_five_item_set_runs_end_to_end_with_tool_calls(tmp_path, items, tokens, api, store):
    summary = go(tmp_path, items, tokens, api, store)
    assert summary.answered == 5
    assert summary.status == "complete"
    assert query(store, "SELECT mode, prompt_id, index_build_hash FROM runs") == [
        ("tools", PROMPT_ID, BUILD)
    ]
    # Each item: one call that asks for the lookup, one that answers.
    assert len(api.messages.calls) == 10
    assert len(query(store, "SELECT * FROM costs")) == 10
    assert query(store, "SELECT name, input_json FROM tool_calls ORDER BY id LIMIT 1") == [
        ("lookup_form", '{"form":"Gallia"}')
    ]
    assert len(query(store, "SELECT * FROM tool_calls")) == 5


def test_the_final_claim_is_judged_by_the_index_and_scored_against_gold(
    tmp_path, items, tokens, api, store
):
    go(tmp_path, items, tokens, api, store)
    rows = query(
        store,
        "SELECT claims.form, verdicts.verdict, scores.exact_match FROM claims"
        " JOIN verdicts ON verdicts.claim_id = claims.id"
        " JOIN scores ON scores.claim_id = claims.id",
    )
    by_form = {form: (verdict, exact) for form, verdict, exact in rows}
    assert by_form["est"] == ("verified", 1)
    assert by_form["omnis"] == ("contradicted", 0)
    assert query(store, "SELECT DISTINCT index_build_hash FROM verdicts") == [(BUILD,)]


def test_a_claim_about_another_word_is_a_format_failure(tmp_path, items, tokens, store):
    other = json.dumps(
        {
            "text": "",
            "claims": [
                {
                    "form": "Galliae",
                    "lemma": "Gallia",
                    "upos": "NOUN",
                    "features": {name: "None" for name in ALLOWED_FEATURES},
                }
            ],
        }
    )
    api = type("Api", (), {"messages": ToolCallingMessages({"Gallia": other})})()
    summary = go(tmp_path, items, tokens, api, store)
    assert summary.failures == 2  # *Gallia* (other word) and *divisa* (not JSON)
    assert query(store, "SELECT COUNT(*) FROM claims WHERE form = 'Galliae'") == [(0,)]


def test_a_stopped_run_resumes_without_asking_again(tmp_path, items, tokens, api, store):
    go(tmp_path, items, tokens, api, store, limit=2)
    asked = len(api.messages.calls)
    summary = go(tmp_path, items, tokens, api, store)
    assert summary.skipped == 2
    assert summary.answered == 3
    assert len(api.messages.calls) == asked + 6


def test_the_prompt_announces_the_tools_and_never_mentions_the_gold():
    assert "lookup_form" in SYSTEM_PROMPT
    assert "gold" not in SYSTEM_PROMPT.lower()
