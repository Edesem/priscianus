"""ADR-004 Decision 9: a response of several API calls, with tool calls and repair attempts."""

import sqlite3

import pytest

from evals.store import EvalStore, RunKey
from tests.test_store_calls import SCORE, call, save_item

KEY = RunKey("parse", "v1", "dev", "verified", "claude-haiku-5-5", "verified-parse-v1")
BUILD = "build-a"

WRONG = {"form": "amat", "lemma": "amo", "upos": "VERB", "features": {"Person": "2"}}
STILL_WRONG = {"form": "amat", "lemma": "amo", "upos": "VERB", "features": {"Person": "1"}}
RIGHT = {"form": "amat", "lemma": "amo", "upos": "VERB", "features": {"Person": "3"}}
MISS = {
    "exact_match": False,
    "lemma_match": True,
    "upos_match": True,
    "features": {"Person": False},
}


@pytest.fixture
def store(tmp_path):
    return EvalStore(tmp_path / "evals.db")


def rows(store, sql):
    return sqlite3.connect(store.path).execute(sql).fetchall()


def record_multi_call(store, run, item_id="perseus/s1/4"):
    """A first pass with two tool calls, then two repair attempts: the second one is right."""
    save_item(store, item_id)
    store.record_response(
        run,
        item_id,
        raw_text='{"text":"it loves","claims":[]}',
        format_error=None,
        claim=RIGHT,
        verdict="verified",
        score=SCORE,
        cost=[
            call(0.002, 400, attempt=0, ordinal=0),
            call(0.003, 500, attempt=0, ordinal=1),
            call(0.004, 600, attempt=1, ordinal=0),
            call(0.005, 700, attempt=2, ordinal=0),
        ],
        index_build_hash=BUILD,
        final_attempt=2,
        final_state="verified",
        tool_limit_hit=False,
        earlier_stages=[
            {"attempt": 0, "claim": WRONG, "verdict": "contradicted", "score": MISS},
            {"attempt": 1, "claim": STILL_WRONG, "verdict": "contradicted", "score": MISS},
        ],
        tool_calls=[
            {
                "attempt": 0,
                "round": 1,
                "name": "lookup_form",
                "input": {"form": "amat"},
                "result": '{"readings":[]}',
                "is_error": False,
            },
            {
                "attempt": 0,
                "round": 1,
                "name": "inflect",
                "input": {"lemma": "amo", "features": {"Person": "9"}},
                "result": '{"error":"invalid_input"}',
                "is_error": True,
            },
            {
                "attempt": 1,
                "round": 1,
                "name": "lookup_form",
                "input": {"form": "amat"},
                "result": '{"readings":[]}',
                "is_error": False,
            },
        ],
        repair_attempts=[
            {
                "attempt": 1,
                "message_text": "The index does not confirm this claim",
                "raw_text": '{"text":"still","claims":[]}',
                "format_error": None,
                "stop_reason": None,
            },
            {
                "attempt": 2,
                "message_text": "Read the sentence again",
                "raw_text": '{"text":"it loves","claims":[]}',
                "format_error": None,
                "stop_reason": "cleared",
            },
        ],
    )


def test_a_multi_call_response_reads_back_whole(store):
    run = store.start_run(KEY, git_commit="a", index_build_hash=BUILD)
    record_multi_call(store, run)
    response = store.read_response(run, "perseus/s1/4")
    assert response.final_state == "verified"
    assert response.tool_limit_hit is False
    assert [(c.attempt, c.is_final, c.claim["features"]["Person"]) for c in response.claims] == [
        (0, False, "2"),
        (1, False, "1"),
        (2, True, "3"),
    ]
    assert [(c.verdict, c.score["exact_match"]) for c in response.claims] == [
        ("contradicted", False),
        ("contradicted", False),
        ("verified", True),
    ]
    assert [(t.attempt, t.round, t.ordinal, t.name, t.is_error) for t in response.tool_calls] == [
        (0, 1, 0, "lookup_form", False),
        (0, 1, 1, "inflect", True),
        (1, 1, 0, "lookup_form", False),
    ]
    assert response.tool_calls[1].input == {"lemma": "amo", "features": {"Person": "9"}}
    assert response.tool_calls[1].result == '{"error":"invalid_input"}'
    assert [(a.attempt, a.stop_reason, a.format_error) for a in response.repair_attempts] == [
        (1, None, None),
        (2, "cleared", None),
    ]
    assert response.repair_attempts[0].message_text == "The index does not confirm this claim"
    assert response.repair_attempts[1].raw_text == '{"text":"it loves","claims":[]}'
    assert [(c["attempt"], c["ordinal"], c["usd"]) for c in response.calls] == [
        (0, 0, 0.002),
        (0, 1, 0.003),
        (1, 0, 0.004),
        (2, 0, 0.005),
    ]


def test_every_stage_has_a_verdict_under_the_run_build_and_a_score(store):
    run = store.start_run(KEY, git_commit="a", index_build_hash=BUILD)
    record_multi_call(store, run)
    assert rows(
        store,
        "SELECT claims.attempt, verdicts.verdict, verdicts.index_build_hash"
        " FROM claims JOIN verdicts ON verdicts.claim_id = claims.id ORDER BY claims.attempt",
    ) == [(0, "contradicted", BUILD), (1, "contradicted", BUILD), (2, "verified", BUILD)]
    assert rows(
        store,
        "SELECT claims.attempt, scores.exact_match FROM claims"
        " JOIN scores ON scores.claim_id = claims.id ORDER BY claims.attempt",
    ) == [(0, 0), (1, 0), (2, 1)]


def test_a_report_sees_one_row_with_the_final_claim_and_every_call_summed(store):
    run = store.start_run(KEY, git_commit="a", index_build_hash=BUILD)
    record_multi_call(store, run)
    (row,) = store.run_rows(run)
    assert row.claim == RIGHT
    assert row.verdict == "verified"
    assert row.score["exact_match"] is True
    assert row.usd == pytest.approx(0.014)
    assert row.latency_ms == 2200


def test_a_failed_repair_attempt_keeps_its_error_and_leaves_the_earlier_claim_final(store):
    run = store.start_run(KEY, git_commit="a", index_build_hash=BUILD)
    save_item(store, "perseus/s1/4")
    store.record_response(
        run,
        "perseus/s1/4",
        raw_text="{}",
        format_error=None,
        claim=WRONG,
        verdict="contradicted",
        score=MISS,
        cost=[call(0.002, 400), call(0.003, 500, attempt=1)],
        index_build_hash=BUILD,
        final_state="disputed",
        repair_attempts=[
            {
                "attempt": 1,
                "message_text": "m",
                "raw_text": "not json",
                "format_error": "invalid JSON",
                "stop_reason": "schema_failure",
            }
        ],
    )
    response = store.read_response(run, "perseus/s1/4")
    assert [(c.attempt, c.is_final) for c in response.claims] == [(0, True)]
    assert response.final_state == "disputed"
    assert response.repair_attempts[0].format_error == "invalid JSON"
    assert response.repair_attempts[0].stop_reason == "schema_failure"


def test_the_tool_limit_is_recorded_on_the_response(store):
    run = store.start_run(KEY, git_commit="a", index_build_hash=BUILD)
    save_item(store, "perseus/s1/4")
    store.record_response(
        run,
        "perseus/s1/4",
        raw_text="{}",
        format_error="invalid JSON",
        claim=None,
        verdict=None,
        score=None,
        cost=[call(0.002, 400)],
        tool_limit_hit=True,
    )
    assert store.read_response(run, "perseus/s1/4").tool_limit_hit is True


def test_reading_a_response_that_is_not_there_raises_key_error(store):
    run = store.start_run(KEY, git_commit="a", index_build_hash=BUILD)
    with pytest.raises(KeyError):
        store.read_response(run, "perseus/s9/9")


def test_a_run_remembers_its_index_build_and_will_not_resume_under_another(store):
    run = store.start_run(KEY, git_commit="a", index_build_hash=BUILD)
    assert store.start_run(KEY, git_commit="b", index_build_hash=BUILD) == run
    with pytest.raises(ValueError, match="build"):
        store.start_run(KEY, git_commit="b", index_build_hash="build-b")
    assert store.run_info(run).index_build_hash == BUILD


def test_a_tools_or_verified_run_needs_an_index_build_but_a_raw_run_does_not(store):
    with pytest.raises(ValueError, match="build"):
        store.start_run(KEY, git_commit="a")
    with pytest.raises(ValueError, match="build"):
        store.start_run(KEY._replace(mode="tools"), git_commit="a")
    assert store.start_run(KEY._replace(mode="raw"), git_commit="a") > 0
