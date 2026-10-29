import sqlite3

import pytest

from evals.store import EvalStore, RunKey

KEY = RunKey("parse", "v1", "dev", "raw", "claude-haiku-5-5", "raw-parse-v3")


@pytest.fixture
def store(tmp_path):
    return EvalStore(tmp_path / "evals.db")


def rows(store, sql):
    return sqlite3.connect(store.path).execute(sql).fetchall()


def test_the_schema_has_the_tables_of_adr_003(store):
    names = {r[0] for r in rows(store, "SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"runs", "items", "responses", "claims", "verdicts", "scores", "costs"} <= names


def test_a_run_records_what_identifies_it(store):
    run = store.start_run(KEY, git_commit="abc123")
    (row,) = rows(
        store,
        "SELECT model, mode, set_name, split, prompt_id, git_commit, started_at, finished_at"
        f" FROM runs WHERE id = {run}",
    )
    assert row[:6] == ("claude-haiku-5-5", "raw", "parse", "dev", "raw-parse-v3", "abc123")
    assert row[6] is not None
    assert row[7] is None


def test_starting_the_same_run_again_resumes_it(store):
    assert store.start_run(KEY, git_commit="a") == store.start_run(KEY, git_commit="b")
    assert len(rows(store, "SELECT * FROM runs")) == 1


def test_another_prompt_or_model_or_split_is_another_run(store):
    first = store.start_run(KEY, git_commit="a")
    other_prompt = store.start_run(KEY._replace(prompt_id="raw-parse-v4"), git_commit="a")
    other_model = store.start_run(KEY._replace(model="claude-sonnet-5-5"), git_commit="a")
    other_split = store.start_run(KEY._replace(split="test"), git_commit="a")
    assert len({first, other_prompt, other_model, other_split}) == 4


def test_finishing_a_run_stamps_its_end_and_status(store):
    run = store.start_run(KEY, git_commit="a")
    store.finish_run(run, "complete")
    assert rows(store, "SELECT status, finished_at IS NOT NULL FROM runs") == [("complete", 1)]


def test_a_resumed_run_is_open_again(store):
    run = store.start_run(KEY, git_commit="a")
    store.finish_run(run, "stopped")
    store.start_run(KEY, git_commit="a")
    assert rows(store, "SELECT status, finished_at FROM runs") == [("running", None)]


def record(store, run, item_id="perseus/s1/4", **overrides):
    fields = dict(
        raw_text='{"lemma": "cano"}',
        format_error=None,
        claim={"form": "cano", "lemma": "cano", "upos": "VERB", "features": {"Person": "1"}},
        verdict="verified",
        score={
            "exact_match": True,
            "lemma_match": True,
            "upos_match": True,
            "features": {"Person": True},
        },
        cost={
            "model": "claude-haiku-5-5",
            "input_tokens": 10,
            "output_tokens": 5,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "usd": 0.001,
            "cache_hit": False,
        },
    )
    fields.update(overrides)
    store.record_response(run, item_id, **fields)


def test_a_recorded_response_is_stored_with_claim_verdict_score_and_cost(store):
    run = store.start_run(KEY, git_commit="a")
    record(store, run)
    assert rows(store, "SELECT item_id, raw_text, format_error FROM responses") == [
        ("perseus/s1/4", '{"lemma": "cano"}', None)
    ]
    assert rows(store, "SELECT form, lemma, upos, features_json FROM claims") == [
        ("cano", "cano", "VERB", '{"Person":"1"}')
    ]
    assert rows(store, "SELECT verdict FROM verdicts") == [("verified",)]
    assert rows(store, "SELECT exact_match, lemma_match, features_json FROM scores") == [
        (1, 1, '{"Person":true}')
    ]
    assert rows(store, "SELECT model, input_tokens, usd, cache_hit FROM costs") == [
        ("claude-haiku-5-5", 10, 0.001, 0)
    ]


def test_a_format_failure_is_stored_without_claim_verdict_or_score(store):
    run = store.start_run(KEY, git_commit="a")
    record(store, run, format_error="invalid JSON", claim=None, verdict=None, score=None)
    assert rows(store, "SELECT format_error FROM responses") == [("invalid JSON",)]
    assert rows(store, "SELECT * FROM claims") == []
    assert rows(store, "SELECT * FROM verdicts") == []
    assert rows(store, "SELECT * FROM scores") == []
    assert len(rows(store, "SELECT * FROM costs")) == 1


def test_answered_items_are_those_with_a_response_in_that_run(store):
    run = store.start_run(KEY, git_commit="a")
    other = store.start_run(KEY._replace(split="test"), git_commit="a")
    record(store, run, "perseus/s1/4")
    record(store, other, "perseus/s9/1")
    assert store.answered_items(run) == {"perseus/s1/4"}


def test_a_failed_response_counts_as_answered(store):
    run = store.start_run(KEY, git_commit="a")
    record(store, run, format_error="x", claim=None, verdict=None, score=None)
    assert store.answered_items(run) == {"perseus/s1/4"}


def test_an_item_is_answered_once_per_run(store):
    run = store.start_run(KEY, git_commit="a")
    record(store, run)
    with pytest.raises(sqlite3.IntegrityError):
        record(store, run)
    assert len(rows(store, "SELECT * FROM responses")) == 1
    assert len(rows(store, "SELECT * FROM costs")) == 1


def test_items_are_stored_once_with_their_strata_and_gold(store):
    item = dict(
        split="dev",
        treebank="perseus",
        sent_id="s1",
        word_id=4,
        slice="Classical",
        pos_class="verb",
        freq_band="top1k",
        gold={"lemma": "cano", "upos": "VERB", "features": {"Person": "1"}},
    )
    store.save_item("perseus/s1/4", **item)
    store.save_item("perseus/s1/4", **item)
    assert rows(store, "SELECT id, slice, pos_class, gold_json FROM items") == [
        (
            "perseus/s1/4",
            "Classical",
            "verb",
            '{"features":{"Person":"1"},"lemma":"cano","upos":"VERB"}',
        )
    ]


def test_run_totals_sum_the_cost_and_count_cache_hits(store):
    run = store.start_run(KEY, git_commit="a")
    record(store, run, "a/1/1")
    cached = dict(
        model="claude-haiku-5-5",
        input_tokens=10,
        output_tokens=5,
        cache_read_tokens=0,
        cache_write_tokens=0,
        usd=0.0,
        cache_hit=True,
    )
    record(store, run, "a/1/2", cost=cached)
    assert store.spent_usd(run) == pytest.approx(0.001)
