"""#77: one report that sets the raw, tools and verified runs side by side."""

import pytest
from priscianus.morphology.lookup import Analysis

from evals.__main__ import main
from evals.report import render_report, repair_harm_items
from evals.store import EvalStore, RunKey

MODEL = "claude-haiku-5-5"
GOLD = {
    "form": "amat",
    "lemma": "amo",
    "upos": "VERB",
    "features": {"Person": "3"},
    "sentence": "SECRET TREEBANK SENTENCE",
}
RIGHT = {"form": "amat", "lemma": "amo", "upos": "VERB", "features": {"Person": "3"}}
WRONG = {"form": "amat", "lemma": "amo", "upos": "VERB", "features": {"Person": "2"}}
HIT = {"exact_match": True, "lemma_match": True, "upos_match": True, "features": {"Person": True}}
MISS = {**HIT, "exact_match": False, "features": {"Person": False}}
COST = {
    "model": MODEL,
    "input_tokens": 1,
    "output_tokens": 1,
    "cache_read_tokens": 0,
    "cache_write_tokens": 0,
    "usd": 0.01,
    "cache_hit": False,
    "latency_ms": 100,
}
TOOL = {"attempt": 0, "round": 1, "name": "lookup_form", "input": {}, "result": "{}", "is_error": 0}
REPAIR = {
    "attempt": 1,
    "message_text": "m",
    "raw_text": "{}",
    "format_error": None,
    "stop_reason": None,
}


class FakeIndex:
    def analyse(self, form):
        return [Analysis(form, "amo", "verb", form, {"Person": "3"})]

    def has_lemma(self, lemma):
        return True


def key(mode, **changes):
    return RunKey("parse", "v1", "dev", mode, MODEL, f"{mode}-parse-v1")._replace(**changes)


def save_item(store, item_id):
    store.save_item(
        item_id, split="dev", treebank="perseus", sent_id=item_id, word_id=1,
        slice="Classical", pos_class="verb", freq_band="top1k", gold=GOLD,
    )  # fmt: skip


def answer(store, run, item_id, claim, verdict, score, **extra):
    save_item(store, item_id)
    store.record_response(
        run, item_id, raw_text="{}", format_error=None, claim=claim, verdict=verdict,
        score=score, cost=COST, **extra,
    )  # fmt: skip


@pytest.fixture
def store(tmp_path):
    """Two items per mode. Raw gets one wrong. Tools makes two tool calls on the first item.
    Verified gets "good" wrong then repaired to right, and "bad" right then repaired to wrong."""
    store = EvalStore(tmp_path / "evals.db")
    raw = store.start_run(key("raw"), git_commit="x")
    answer(store, raw, "perseus/good/1", WRONG, "contradicted", MISS)
    answer(store, raw, "perseus/bad/1", RIGHT, "verified", HIT)
    tools = store.start_run(key("tools"), git_commit="x", index_build_hash="b1")
    answer(store, tools, "perseus/good/1", RIGHT, "verified", HIT, tool_calls=[TOOL, TOOL])
    answer(store, tools, "perseus/bad/1", RIGHT, "verified", HIT)
    verified = store.start_run(key("verified"), git_commit="x", index_build_hash="b1")
    answer(
        store, verified, "perseus/good/1", RIGHT, "verified", HIT,
        index_build_hash="b1", final_attempt=1, repair_attempts=[REPAIR],
        earlier_stages=[{"attempt": 0, "claim": WRONG, "verdict": "contradicted", "score": MISS}],
    )  # fmt: skip
    answer(
        store, verified, "perseus/bad/1", WRONG, "contradicted", MISS,
        index_build_hash="b1", final_attempt=1, repair_attempts=[REPAIR],
        earlier_stages=[{"attempt": 0, "claim": RIGHT, "verdict": "contradicted", "score": HIT}],
    )  # fmt: skip
    return store


def report(store, runs, **kwargs):
    infos = [store.run_info(r) for r in runs]
    return render_report(
        [(i, store.run_rows(r)) for i, r in zip(infos, runs, strict=True)],
        FakeIndex(),
        first_passes={r: store.first_passes(r) for r in runs},
        tool_calls={r: store.tool_call_counts(r) for r in runs},
        **kwargs,
    )


def line_with(text, *parts):
    return next(line for line in text.splitlines() if all(p in line for p in parts))


def test_one_table_has_a_row_per_mode_with_cost_tool_calls_and_repair(store):
    text = report(store, [1, 2, 3])
    assert line_with(text, "| raw |").count("50.0% (1/2)") >= 1
    tools = line_with(text, "| tools |")
    assert "1.0" in tools and "$0.0100" in tools  # 2 tool calls over 2 items
    verified = line_with(text, "| verified |")
    assert "1 / 1" in verified  # repair success and harm are one each
    assert "–" in line_with(text, "| raw |")  # no repair in raw mode


def test_the_breakdowns_are_shown_for_every_mode(store):
    text = report(store, [1, 2, 3])
    for run_id, mode in ((1, "raw"), (2, "tools"), (3, "verified")):
        assert f"## Run {run_id}: {mode} mode" in text
    assert text.count("### By frequency band") == 3
    assert text.count("### By pos class") == 3
    assert text.count("### By classical / ecclesiastical") == 3


@pytest.mark.parametrize("change", [{"split": "test"}, {"manifest_version": "v2"}])
def test_runs_from_different_splits_or_manifests_are_never_pooled(store, change):
    other = store.start_run(key("tools", **change), git_commit="x", index_build_hash="b1")
    with pytest.raises(ValueError, match="pool"):
        report(store, [1, other])


def test_repair_harm_lists_item_ids_and_index_readings_but_no_treebank_text(store):
    harmed = repair_harm_items(store.run_rows(3), store.first_passes(3))
    assert [r.item_id for r in harmed] == ["perseus/bad/1"]
    text = report(store, [1, 2, 3])
    section = text.split("## Repair harm")[1]
    assert "perseus/bad/1" in section and "Person=3" in section
    assert "perseus/good/1" not in section
    assert "SECRET TREEBANK SENTENCE" not in section


def test_the_cli_refuses_to_pool_runs_from_different_splits(store, tmp_path, capsys):
    store.start_run(key("tools", split="test"), git_commit="x", index_build_hash="b1")
    code = main(
        ["report", "1", "4", "--store", str(tmp_path / "evals.db"), "--manifest", "none.jsonl"],
        index=FakeIndex(),
    )
    assert code == 2
    assert "pool" in capsys.readouterr().err
