"""ADR-004, Decision 9: the new columns and tables are additive, so a raw run stored before them
still loads."""

import sqlite3

import pytest

from evals.store import EvalStore, RunKey

# The schema as ADR-003 left it (with `latency_ms`), before #74.
LEGACY = """
CREATE TABLE runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, set_name TEXT NOT NULL, manifest_version TEXT NOT NULL,
    split TEXT NOT NULL, mode TEXT NOT NULL, model TEXT NOT NULL, prompt_id TEXT NOT NULL,
    git_commit TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    UNIQUE (set_name, manifest_version, split, mode, model, prompt_id)
);
CREATE TABLE items (
    id TEXT PRIMARY KEY, split TEXT NOT NULL, treebank TEXT NOT NULL, sent_id TEXT NOT NULL,
    word_id INTEGER NOT NULL, slice TEXT NOT NULL, pos_class TEXT NOT NULL,
    freq_band TEXT NOT NULL, gold_json TEXT NOT NULL
);
CREATE TABLE responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER NOT NULL REFERENCES runs(id),
    item_id TEXT NOT NULL, raw_text TEXT NOT NULL, format_error TEXT, UNIQUE (run_id, item_id)
);
CREATE TABLE claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT, response_id INTEGER NOT NULL REFERENCES responses(id),
    form TEXT NOT NULL, lemma TEXT NOT NULL, upos TEXT NOT NULL, features_json TEXT NOT NULL
);
CREATE TABLE verdicts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, claim_id INTEGER NOT NULL REFERENCES claims(id),
    verdict TEXT NOT NULL
);
CREATE TABLE scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT, response_id INTEGER NOT NULL REFERENCES responses(id),
    exact_match INTEGER NOT NULL, lemma_match INTEGER NOT NULL, upos_match INTEGER NOT NULL,
    features_json TEXT NOT NULL
);
CREATE TABLE costs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, response_id INTEGER NOT NULL REFERENCES responses(id),
    model TEXT NOT NULL, input_tokens INTEGER NOT NULL, output_tokens INTEGER NOT NULL,
    cache_read_tokens INTEGER NOT NULL, cache_write_tokens INTEGER NOT NULL, usd REAL NOT NULL,
    cache_hit INTEGER NOT NULL, latency_ms INTEGER NOT NULL DEFAULT 0
);
INSERT INTO runs VALUES (1, 'parse', 'v1', 'dev', 'raw', 'claude-haiku-5-5', 'raw-parse-v3',
    'abc', '2026-10-29T20:00:00+00:00', '2026-10-29T20:05:00+00:00', 'complete');
INSERT INTO items VALUES ('perseus/s1/4', 'dev', 'perseus', 's1', 4, 'Classical', 'verb',
    'top1k', '{"features":{"Person":"1"},"form":"cano","lemma":"cano","upos":"VERB"}');
INSERT INTO responses VALUES (1, 1, 'perseus/s1/4', '{"text":"x"}', NULL);
INSERT INTO claims VALUES (1, 1, 'cano', 'cano', 'VERB', '{"Person":"1"}');
INSERT INTO verdicts VALUES (1, 1, 'verified');
INSERT INTO scores VALUES (1, 1, 1, 1, 1, '{"Person":true}');
INSERT INTO costs VALUES (1, 1, 'claude-haiku-5-5', 10, 5, 0, 0, 0.001, 0, 250);
"""

KEY = RunKey("parse", "v1", "dev", "raw", "claude-haiku-5-5", "raw-parse-v3")


@pytest.fixture
def legacy_path(tmp_path):
    path = tmp_path / "evals.db"
    con = sqlite3.connect(path)
    con.executescript(LEGACY)
    con.commit()
    con.close()
    return path


def columns(path, table):
    con = sqlite3.connect(path)
    try:
        return {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
    finally:
        con.close()


def test_an_old_store_gains_the_columns_without_losing_a_row(legacy_path):
    EvalStore(legacy_path)
    assert {"attempt", "is_final"} <= columns(legacy_path, "claims")
    assert "tool_calls" in {
        r[0]
        for r in sqlite3.connect(legacy_path).execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }


def test_opening_a_store_twice_changes_nothing(legacy_path):
    EvalStore(legacy_path)
    EvalStore(legacy_path)
    assert len(EvalStore(legacy_path).run_rows(1)) == 1


def test_a_raw_run_stored_before_the_change_loads_as_it_was(legacy_path):
    store = EvalStore(legacy_path)
    (row,) = store.run_rows(1)
    assert row.item_id == "perseus/s1/4"
    assert row.claim == {
        "form": "cano",
        "lemma": "cano",
        "upos": "VERB",
        "features": {"Person": "1"},
    }
    assert row.verdict == "verified"
    assert row.score == {
        "exact_match": True,
        "lemma_match": True,
        "upos_match": True,
        "features": {"Person": True},
    }
    assert (row.usd, row.cache_hit, row.latency_ms) == (0.001, False, 250)
    assert store.run_info(1).mode == "raw"


def test_a_response_stored_before_the_change_reads_back_with_its_score(legacy_path):
    (claim,) = EvalStore(legacy_path).read_response(1, "perseus/s1/4").claims
    assert claim.score == {
        "exact_match": True,
        "lemma_match": True,
        "upos_match": True,
        "features": {"Person": True},
    }
    assert (claim.attempt, claim.is_final, claim.verdict) == (0, True, "verified")
