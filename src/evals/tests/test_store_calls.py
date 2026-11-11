"""ADR-003 Decision 8: `costs` holds one row per API call, and a report sees one row per item."""

import sqlite3

import pytest

from evals.report import headline
from evals.store import EvalStore, RunKey

KEY = RunKey("parse", "v1", "dev", "verified", "claude-haiku-5-5", "verified-parse-v1")


@pytest.fixture
def store(tmp_path):
    return EvalStore(tmp_path / "evals.db")


def rows(store, sql):
    return sqlite3.connect(store.path).execute(sql).fetchall()


def call(usd, latency_ms, *, attempt=0, ordinal=0, cache_hit=False, list_usd=None, **extra):
    return {
        "model": "claude-haiku-5-5",
        "input_tokens": 100,
        "output_tokens": 20,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "usd": usd,
        "cache_hit": cache_hit,
        "latency_ms": latency_ms,
        "attempt": attempt,
        "ordinal": ordinal,
        "list_usd": usd if list_usd is None else list_usd,
        "list_latency_ms": latency_ms,
        **extra,
    }


def save_item(store, item_id):
    store.save_item(
        item_id,
        split="dev",
        treebank="perseus",
        sent_id="s1",
        word_id=int(item_id.rsplit("/", 1)[1]),
        slice="Classical",
        pos_class="verb",
        freq_band="top1k",
        gold={
            "form": "cano",
            "lemma": "cano",
            "upos": "VERB",
            "features": {"Person": "1"},
            "sentence": "Arma virumque cano.",
        },
    )


CLAIM = {"form": "cano", "lemma": "cano", "upos": "VERB", "features": {"Person": "1"}}
SCORE = {"exact_match": True, "lemma_match": True, "upos_match": True, "features": {"Person": True}}


def record(store, run, item_id, costs):
    save_item(store, item_id)
    store.record_response(
        run,
        item_id,
        raw_text="{}",
        format_error=None,
        claim=CLAIM,
        verdict="verified",
        score=SCORE,
        cost=costs,
    )


def test_every_api_call_of_a_response_has_its_own_cost_row(store):
    run = store.start_run(KEY, git_commit="a", index_build_hash="b")
    record(
        store,
        run,
        "perseus/s1/4",
        [
            call(0.002, 400, attempt=0, ordinal=0),
            call(0.003, 600, attempt=0, ordinal=1),
            call(0.004, 800, attempt=1, ordinal=0),
        ],
    )
    assert rows(
        store, "SELECT attempt, ordinal, usd, latency_ms, list_usd FROM costs ORDER BY id"
    ) == [(0, 0, 0.002, 400, 0.002), (0, 1, 0.003, 600, 0.003), (1, 0, 0.004, 800, 0.004)]


def test_a_cache_hit_keeps_its_list_price_beside_the_zero_it_cost(store):
    run = store.start_run(KEY, git_commit="a", index_build_hash="b")
    record(store, run, "perseus/s1/4", [call(0.0, 400, cache_hit=True, list_usd=0.002)])
    assert rows(store, "SELECT usd, list_usd, list_latency_ms, cache_hit FROM costs") == [
        (0.0, 0.002, 400, 1)
    ]


def test_one_call_given_as_a_single_dict_is_still_one_row_at_attempt_zero(store):
    run = store.start_run(KEY, git_commit="a", index_build_hash="b")
    single = {k: v for k, v in call(0.001, 250).items() if k not in ("attempt", "ordinal")}
    record(store, run, "perseus/s1/4", single)
    assert rows(store, "SELECT attempt, ordinal, list_usd FROM costs") == [(0, 0, 0.001)]


def test_an_item_is_one_row_with_its_calls_summed(store):
    run = store.start_run(KEY, git_commit="a", index_build_hash="b")
    record(
        store,
        run,
        "perseus/s1/4",
        [call(0.002, 400), call(0.003, 600, ordinal=1), call(0.004, 800, attempt=1)],
    )
    (row,) = store.run_rows(run)
    assert row.usd == pytest.approx(0.009)
    assert row.latency_ms == 1800
    assert row.cache_hit is False


def test_an_item_is_a_cache_hit_only_if_every_call_was(store):
    run = store.start_run(KEY, git_commit="a", index_build_hash="b")
    record(store, run, "perseus/s1/4", [call(0, 400, cache_hit=True), call(0, 600, cache_hit=True)])
    record(store, run, "perseus/s1/5", [call(0, 400, cache_hit=True), call(0.003, 600)])
    first, second = store.run_rows(run)
    assert (first.cache_hit, second.cache_hit) == (True, False)


def test_run_totals_and_latency_percentiles_are_per_item(store):
    run = store.start_run(KEY, git_commit="a", index_build_hash="b")
    record(store, run, "perseus/s1/1", [call(0.001, 100)])
    record(store, run, "perseus/s1/2", [call(0.001, 100), call(0.001, 100, ordinal=1)])
    record(store, run, "perseus/s1/3", [call(0.001, 100)] * 3)
    summary = headline(store.run_rows(run))
    assert summary.n == 3
    assert summary.usd == pytest.approx(0.006)
    assert (summary.latency_p50_ms, summary.latency_p95_ms) == (200, 300)
    assert store.spent_usd(run) == pytest.approx(0.006)
