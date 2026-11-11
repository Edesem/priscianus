"""`evals score --run <id>`: judge the stored claims again against the index, with no API calls."""

import sqlite3

import pytest

from evals.__main__ import main
from evals.reverify import reverify_run
from evals.store import EvalStore, RunKey
from tests.test_run import FakeIndex
from tests.test_store_calls import SCORE, call, save_item

RAW = RunKey("parse", "v1", "dev", "raw", "claude-haiku-5-5", "raw-parse-v3")
VERIFIED = RunKey("parse", "v1", "dev", "verified", "claude-haiku-5-5", "verified-parse-v1")
OLD, NEW = "build-old", "build-new"

# What FakeIndex has for "est": the claim below is VERIFIED against it, the wrong one CONTRADICTED.
EST = {
    "form": "est",
    "lemma": "sum",
    "upos": "VERB",
    "features": {
        "Mood": "Ind",
        "Person": "3",
        "Number": "Sing",
        "Tense": "Pres",
        "VerbForm": "Fin",
        "Voice": "Act",
    },
}
EST_WRONG = {**EST, "features": {**EST["features"], "Person": "1"}}


class NewIndex(FakeIndex):
    build_hash = NEW


@pytest.fixture
def store(tmp_path):
    return EvalStore(tmp_path / "evals.db")


def rows(store, sql):
    return sqlite3.connect(store.path).execute(sql).fetchall()


def record_raw(store, run, item_id, claim, verdict, **overrides):
    save_item(store, item_id)
    fields = dict(
        raw_text="{}",
        format_error=None,
        claim=claim,
        verdict=verdict,
        score=SCORE,
        cost=call(0.001, 100),
    )
    fields.update(overrides)
    store.record_response(run, item_id, **fields)


def test_a_stored_claim_gets_a_verdict_under_the_new_build(store):
    run = store.start_run(RAW, git_commit="a")
    record_raw(store, run, "perseus/s1/2", EST, "contradicted")  # stored verdict was stale
    summary = reverify_run(store, run, FakeIndex(), NEW)
    assert (summary.claims, summary.changed) == (1, 1)
    assert rows(store, "SELECT verdict, index_build_hash FROM verdicts ORDER BY id") == [
        ("contradicted", None),
        ("verified", NEW),
    ]


def test_the_verdicts_stored_with_the_run_are_not_overwritten(store):
    run = store.start_run(RAW, git_commit="a")
    record_raw(store, run, "perseus/s1/2", EST, "contradicted")
    reverify_run(store, run, FakeIndex(), NEW)
    assert [r.verdict for r in store.run_rows(run)] == ["contradicted"]
    assert [r.verdict for r in store.run_rows(run, verdicts_under=NEW)] == ["verified"]


def test_scoring_again_under_the_same_build_does_not_add_verdicts(store):
    run = store.start_run(RAW, git_commit="a")
    record_raw(store, run, "perseus/s1/2", EST, "verified")
    reverify_run(store, run, FakeIndex(), NEW)
    summary = reverify_run(store, run, FakeIndex(), NEW)
    assert summary.changed == 0
    assert rows(store, f"SELECT COUNT(*) FROM verdicts WHERE index_build_hash = '{NEW}'") == [(1,)]


def test_every_stage_of_a_verified_response_is_judged_again(store):
    run = store.start_run(VERIFIED, git_commit="a", index_build_hash=OLD)
    save_item(store, "perseus/s1/2")
    store.record_response(
        run,
        "perseus/s1/2",
        raw_text="{}",
        format_error=None,
        claim=EST,
        verdict="verified",
        score=SCORE,
        cost=[call(0.001, 100), call(0.001, 100, attempt=1)],
        index_build_hash=OLD,
        final_attempt=1,
        earlier_stages=[
            {"attempt": 0, "claim": EST_WRONG, "verdict": "contradicted", "score": SCORE}
        ],
    )
    summary = reverify_run(store, run, FakeIndex(), NEW)
    assert (summary.claims, summary.changed) == (2, 0)
    assert rows(
        store,
        "SELECT claims.attempt, verdicts.verdict FROM verdicts JOIN claims"
        f" ON claims.id = verdicts.claim_id WHERE verdicts.index_build_hash = '{NEW}'"
        " ORDER BY claims.attempt",
    ) == [(0, "contradicted"), (1, "verified")]


def test_the_readings_behind_a_verdict_are_kept(store):
    run = store.start_run(RAW, git_commit="a")
    record_raw(store, run, "perseus/s1/2", EST_WRONG, "contradicted")
    reverify_run(store, run, FakeIndex(), NEW)
    (readings,) = rows(
        store, f"SELECT readings_json FROM verdicts WHERE index_build_hash = '{NEW}'"
    )
    assert '"lemma":"sum"' in readings[0]


def test_a_format_failure_has_no_claim_to_judge(store):
    run = store.start_run(RAW, git_commit="a")
    record_raw(store, run, "perseus/s1/2", None, None, format_error="invalid JSON", score=None)
    assert reverify_run(store, run, FakeIndex(), NEW).claims == 0


def run_score(tmp_path, *extra, index=None):
    def no_client(**_):
        raise AssertionError("scoring must not call the model")

    return main(
        ["score", "--store", str(tmp_path / "evals.db"), *extra],
        make_client=no_client,
        index=index or NewIndex(),
    )


def test_the_score_command_judges_a_run_again_without_the_client(tmp_path, capsys):
    store = EvalStore(tmp_path / "evals.db")
    run = store.start_run(RAW, git_commit="a")
    record_raw(store, run, "perseus/s1/2", EST, "contradicted")
    assert run_score(tmp_path, "--run", str(run)) == 0
    out = capsys.readouterr().out
    assert f"Run {run}" in out
    assert "1 claim" in out
    assert "1 changed" in out
    assert NEW in out
    assert [r.verdict for r in store.run_rows(run, verdicts_under=NEW)] == ["verified"]


def test_the_score_command_says_so_for_a_run_that_is_not_there(tmp_path, capsys):
    EvalStore(tmp_path / "evals.db")
    assert run_score(tmp_path, "--run", "9") == 2
    assert "no run 9" in capsys.readouterr().err


def test_the_report_can_show_the_verdicts_of_a_new_build(tmp_path, capsys):
    store = EvalStore(tmp_path / "evals.db")
    run = store.start_run(RAW, git_commit="a")
    record_raw(store, run, "perseus/s1/2", EST, "contradicted")
    run_score(tmp_path, "--run", str(run))
    capsys.readouterr()
    common = ["report", str(run), "--store", str(tmp_path / "evals.db")]
    common += ["--manifest", str(tmp_path / "none.jsonl")]
    assert main(common, index=NewIndex()) == 0
    stored = capsys.readouterr().out
    assert main([*common, "--rescored"], index=NewIndex()) == 0
    rescored = capsys.readouterr().out
    assert stored != rescored
