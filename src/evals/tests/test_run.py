import json
import sqlite3

import pytest
from anthropic.types import Message, TextBlock
from anthropic.types import Usage as AnthropicUsage
from priscianus.llm.client import LLMClient
from priscianus.morphology.lookup import Analysis

from evals.gold import parse_conllu
from evals.parse_set import Item
from evals.raw_prompt import ALLOWED_FEATURES, PROMPT_ID
from evals.run import run_parse
from evals.store import EvalStore

MODEL = "claude-haiku-5-5"

CONLLU = """\
# sent_id = s1
# text = Gallia est omnis divisa in partes tres
1\tGallia\tGallia\tNOUN\t_\tCase=Nom|Gender=Fem|Number=Sing\t5\tnsubj\t_\t_
2\test\tsum\tAUX\t_\tMood=Ind|Number=Sing|Person=3|Tense=Pres|VerbForm=Fin|Voice=Act\t5\tcop\t_\t_
3\tomnis\tomnis\tADJ\t_\tCase=Nom|Gender=Fem|Number=Sing\t1\tamod\t_\t_
4\tdivisa\tdivido\tVERB\t_\tCase=Nom|Gender=Fem|Number=Sing|Tense=Past|VerbForm=Part|Voice=Pass\t0\troot\t_\t_
5\tin\tin\tADP\t_\t_\t6\tcase\t_\t_

"""

# What the fake model answers for each target: the first two are right, *omnis* has the wrong
# case, *divisa* is not valid JSON, *in* is right.
ANSWERS = {
    "Gallia": ("Gallia", "NOUN", {"Case": "Nom", "Number": "Sing", "Gender": "Fem"}),
    "est": (
        "sum",
        "AUX",
        {
            "Mood": "Ind",
            "Person": "3",
            "Number": "Sing",
            "Tense": "Pres",
            "VerbForm": "Fin",
            "Voice": "Act",
        },
    ),
    "omnis": ("omnis", "ADJ", {"Case": "Acc", "Number": "Sing", "Gender": "Fem"}),
    "in": ("in", "ADP", {}),
}


class FakeIndex:
    def analyse(self, form):
        if form == "est":
            return [
                Analysis(
                    "sum",
                    "sum",
                    "verb",
                    "est",
                    {
                        "Mood": "Ind",
                        "Person": "3",
                        "Number": "Sing",
                        "Tense": "Pres",
                        "VerbForm": "Fin",
                        "Voice": "Act",
                    },
                )
            ]
        return []

    def has_lemma(self, lemma):
        return lemma in {"sum", "omnis"}


class FakeMessages:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        content = kwargs["messages"][0]["content"]
        form = content.split('Word to analyse: "')[1].split('"')[0]
        if form in ANSWERS:
            lemma, upos, given = ANSWERS[form]
            features = {name: given.get(name, "None") for name in ALLOWED_FEATURES}
            text = json.dumps({"lemma": lemma, "upos": upos, "features": features})
        else:
            text = "not json"
        return Message(
            id="m",
            type="message",
            role="assistant",
            model=MODEL,
            content=[TextBlock(type="text", text=text)],
            stop_reason="end_turn",
            stop_sequence=None,
            usage=AnthropicUsage(input_tokens=1000, output_tokens=100),
        )


@pytest.fixture
def tokens():
    return parse_conllu(CONLLU, treebank="perseus")


@pytest.fixture
def items(tokens):
    return [Item("dev", t, "Classical", "perseus", "verb", "top1k") for t in tokens]


@pytest.fixture
def api():
    return type("Api", (), {"messages": FakeMessages()})()


@pytest.fixture
def store(tmp_path):
    return EvalStore(tmp_path / "evals.db")


def client_for(tmp_path, api, **kwargs):
    return LLMClient(api, db_path=tmp_path / "llm.db", **kwargs)


def go(tmp_path, items, tokens, api, store, **kwargs):
    return run_parse(
        items,
        tokens,
        client_for(tmp_path, api, **kwargs.pop("client", {})),
        FakeIndex(),
        store,
        model=MODEL,
        manifest_version="v1",
        split=kwargs.pop("split", "dev"),
        git_commit="abc",
        **kwargs,
    )


def query(store, sql):
    return sqlite3.connect(store.path).execute(sql).fetchall()


def test_a_five_item_set_runs_end_to_end(tmp_path, items, tokens, api, store):
    summary = go(tmp_path, items, tokens, api, store)
    assert summary.answered == 5
    assert summary.status == "complete"
    assert len(api.messages.calls) == 5
    assert query(store, "SELECT status, git_commit, prompt_id FROM runs") == [
        ("complete", "abc", PROMPT_ID)
    ]
    assert len(query(store, "SELECT * FROM responses")) == 5
    assert len(query(store, "SELECT * FROM items")) == 5
    assert len(query(store, "SELECT * FROM costs")) == 5


def test_each_response_is_scored_against_gold_when_written(tmp_path, items, tokens, api, store):
    go(tmp_path, items, tokens, api, store)
    exact = dict(
        query(
            store,
            "SELECT responses.item_id, scores.exact_match FROM scores"
            " JOIN responses ON responses.id = scores.response_id",
        )
    )
    # *divisa* got "not json", so it has no score; *omnis* has the wrong case.
    assert exact == {
        "perseus/s1/1": 1,
        "perseus/s1/2": 1,
        "perseus/s1/3": 0,
        "perseus/s1/5": 1,
    }


def test_each_claim_gets_a_verdict_from_the_index(tmp_path, items, tokens, api, store):
    go(tmp_path, items, tokens, api, store)
    verdicts = dict(
        query(
            store,
            "SELECT claims.form, verdicts.verdict FROM verdicts"
            " JOIN claims ON claims.id = verdicts.claim_id",
        )
    )
    assert verdicts["est"] == "verified"
    assert verdicts["omnis"] == "contradicted"


def test_a_response_that_is_not_a_claim_is_stored_as_a_format_failure(
    tmp_path, items, tokens, api, store
):
    summary = go(tmp_path, items, tokens, api, store)
    assert summary.failures == 1
    assert query(
        store, "SELECT item_id, raw_text FROM responses WHERE format_error IS NOT NULL"
    ) == [("perseus/s1/4", "not json")]


def test_cost_is_computed_from_usage(tmp_path, items, tokens, api, store):
    go(tmp_path, items, tokens, api, store)
    # 1000 input and 100 output tokens at Haiku prices, five times.
    assert store.spent_usd(1) == pytest.approx(5 * (1000 * 0.10 + 100 * 0.50) / 1_000_000)


def test_a_rerun_skips_items_already_answered(tmp_path, items, tokens, api, store):
    go(tmp_path, items, tokens, api, store)
    summary = go(tmp_path, items, tokens, api, store)
    assert summary.answered == 0
    assert summary.skipped == 5
    assert len(api.messages.calls) == 5
    assert len(query(store, "SELECT * FROM runs")) == 1


def test_an_interrupted_run_resumes_with_the_missing_items(tmp_path, items, tokens, api, store):
    go(tmp_path, items, tokens, api, store, limit=2)
    summary = go(tmp_path, items, tokens, api, store)
    assert summary.skipped == 2
    assert summary.answered == 3
    assert len(query(store, "SELECT * FROM responses")) == 5


def test_a_response_the_client_has_cached_is_free(tmp_path, items, tokens, api, store):
    go(tmp_path, items, tokens, api, store)
    other = EvalStore(tmp_path / "other.db")
    go(tmp_path, items, tokens, api, other)
    assert len(api.messages.calls) == 5
    assert other.spent_usd(1) == 0
    assert query(other, "SELECT DISTINCT cache_hit FROM costs") == [(1,)]


def test_limit_stops_after_that_many_items(tmp_path, items, tokens, api, store):
    summary = go(tmp_path, items, tokens, api, store, limit=3)
    assert summary.answered == 3
    assert len(api.messages.calls) == 3


def test_only_items_of_the_split_are_run(tmp_path, items, tokens, api, store):
    mixed = [items[0], Item("test", items[1].token, "Classical", "perseus", "verb", "top1k")]
    summary = go(tmp_path, mixed, tokens, api, store, split="test")
    assert summary.answered == 1
    assert query(store, "SELECT item_id FROM responses") == [("perseus/s1/2",)]


def test_concurrent_runs_answer_every_item_once(tmp_path, items, tokens, api, store):
    summary = go(tmp_path, items, tokens, api, store, concurrency=3)
    assert summary.answered == 5
    assert len(query(store, "SELECT DISTINCT item_id FROM responses")) == 5


def test_the_run_stops_when_the_cost_cap_is_reached(tmp_path, items, tokens, api, store):
    summary = go(tmp_path, items, tokens, api, store, client={"spend_cap_usd": 0.0001})
    # One call costs $0.00015, which crosses the cap, so no second call starts.
    assert summary.answered == 1
    assert summary.status == "stopped: max cost"
    assert query(store, "SELECT status FROM runs") == [("stopped: max cost",)]
