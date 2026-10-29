"""The eval store: SQLite holding every run, response, claim, verdict, score and cost (ADR-003)."""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NamedTuple

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    set_name TEXT NOT NULL,
    manifest_version TEXT NOT NULL,
    split TEXT NOT NULL,
    mode TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_id TEXT NOT NULL,
    git_commit TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    UNIQUE (set_name, manifest_version, split, mode, model, prompt_id)
);
CREATE TABLE IF NOT EXISTS items (
    id TEXT PRIMARY KEY,
    split TEXT NOT NULL,
    treebank TEXT NOT NULL,
    sent_id TEXT NOT NULL,
    word_id INTEGER NOT NULL,
    slice TEXT NOT NULL,
    pos_class TEXT NOT NULL,
    freq_band TEXT NOT NULL,
    gold_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES runs(id),
    item_id TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    format_error TEXT,
    UNIQUE (run_id, item_id)
);
CREATE TABLE IF NOT EXISTS claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    response_id INTEGER NOT NULL REFERENCES responses(id),
    form TEXT NOT NULL,
    lemma TEXT NOT NULL,
    upos TEXT NOT NULL,
    features_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS verdicts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id INTEGER NOT NULL REFERENCES claims(id),
    verdict TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    response_id INTEGER NOT NULL REFERENCES responses(id),
    exact_match INTEGER NOT NULL,
    lemma_match INTEGER NOT NULL,
    upos_match INTEGER NOT NULL,
    features_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS costs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    response_id INTEGER NOT NULL REFERENCES responses(id),
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cache_read_tokens INTEGER NOT NULL,
    cache_write_tokens INTEGER NOT NULL,
    usd REAL NOT NULL,
    cache_hit INTEGER NOT NULL,
    latency_ms INTEGER NOT NULL DEFAULT 0
);
"""


class Row(NamedTuple):
    """One answered item with everything stored about it. A format failure has no claim."""

    item_id: str
    slice: str
    pos_class: str
    freq_band: str
    gold: dict[str, Any]
    raw_text: str
    format_error: str | None
    claim: dict[str, Any] | None
    verdict: str | None
    score: dict[str, Any] | None
    usd: float
    cache_hit: bool
    latency_ms: int


class RunKey(NamedTuple):
    """What identifies a run. Running the same key again resumes the run."""

    set_name: str
    manifest_version: str
    split: str
    mode: str
    model: str
    prompt_id: str


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class EvalStore:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self.path)
        self._db.executescript(_SCHEMA)
        columns = {r[1] for r in self._db.execute("PRAGMA table_info(costs)")}
        if "latency_ms" not in columns:
            self._db.execute("ALTER TABLE costs ADD COLUMN latency_ms INTEGER NOT NULL DEFAULT 0")

    def start_run(self, key: RunKey, *, git_commit: str) -> int:
        """Start the run for `key`, or reopen it if it exists, and return its ID."""
        with self._db:
            row = self._db.execute(
                "SELECT id FROM runs WHERE set_name = ? AND manifest_version = ? AND split = ?"
                " AND mode = ? AND model = ? AND prompt_id = ?",
                key,
            ).fetchone()
            if row:
                self._db.execute(
                    "UPDATE runs SET status = 'running', finished_at = NULL WHERE id = ?", row
                )
                return int(row[0])
            cursor = self._db.execute(
                "INSERT INTO runs(set_name, manifest_version, split, mode, model, prompt_id,"
                " git_commit, started_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (*key, git_commit, _now()),
            )
            assert cursor.lastrowid is not None
            return cursor.lastrowid

    def finish_run(self, run_id: int, status: str) -> None:
        with self._db:
            self._db.execute(
                "UPDATE runs SET status = ?, finished_at = ? WHERE id = ?", (status, _now(), run_id)
            )

    def save_item(
        self,
        item_id: str,
        *,
        split: str,
        treebank: str,
        sent_id: str,
        word_id: int,
        slice: str,
        pos_class: str,
        freq_band: str,
        gold: dict[str, Any],
    ) -> None:
        with self._db:
            self._db.execute(
                "INSERT OR REPLACE INTO items(id, split, treebank, sent_id, word_id, slice,"
                " pos_class, freq_band, gold_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    item_id,
                    split,
                    treebank,
                    sent_id,
                    word_id,
                    slice,
                    pos_class,
                    freq_band,
                    _json(gold),
                ),
            )

    def answered_items(self, run_id: int) -> set[str]:
        rows = self._db.execute("SELECT item_id FROM responses WHERE run_id = ?", (run_id,))
        return {r[0] for r in rows}

    def spent_usd(self, run_id: int) -> float:
        row = self._db.execute(
            "SELECT COALESCE(SUM(costs.usd), 0) FROM costs"
            " JOIN responses ON responses.id = costs.response_id WHERE responses.run_id = ?",
            (run_id,),
        ).fetchone()
        return float(row[0])

    def spent_usd_for(self, key: RunKey) -> float:
        """What the run for `key` has cost so far; 0 if it has not started."""
        row = self._db.execute(
            "SELECT id FROM runs WHERE set_name = ? AND manifest_version = ? AND split = ?"
            " AND mode = ? AND model = ? AND prompt_id = ?",
            key,
        ).fetchone()
        return self.spent_usd(row[0]) if row else 0.0

    def record_response(
        self,
        run_id: int,
        item_id: str,
        *,
        raw_text: str,
        format_error: str | None,
        claim: dict[str, Any] | None,
        verdict: str | None,
        score: dict[str, Any] | None,
        cost: dict[str, Any],
    ) -> None:
        """Store one answered item whole: the response, and its claim, verdict, score and cost.

        A response with a `format_error` has no claim, verdict or score. Raises
        `sqlite3.IntegrityError` if the run already has a response for the item.
        """
        with self._db:
            response_id = self._db.execute(
                "INSERT INTO responses(run_id, item_id, raw_text, format_error)"
                " VALUES (?, ?, ?, ?)",
                (run_id, item_id, raw_text, format_error),
            ).lastrowid
            if claim is not None:
                claim_id = self._db.execute(
                    "INSERT INTO claims(response_id, form, lemma, upos, features_json)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (
                        response_id,
                        claim["form"],
                        claim["lemma"],
                        claim["upos"],
                        _json(claim["features"]),
                    ),
                ).lastrowid
                if verdict is not None:
                    self._db.execute(
                        "INSERT INTO verdicts(claim_id, verdict) VALUES (?, ?)", (claim_id, verdict)
                    )
            if score is not None:
                self._db.execute(
                    "INSERT INTO scores(response_id, exact_match, lemma_match, upos_match,"
                    " features_json) VALUES (?, ?, ?, ?, ?)",
                    (
                        response_id,
                        int(score["exact_match"]),
                        int(score["lemma_match"]),
                        int(score["upos_match"]),
                        _json(score["features"]),
                    ),
                )
            self._db.execute(
                "INSERT INTO costs(response_id, model, input_tokens, output_tokens,"
                " cache_read_tokens, cache_write_tokens, usd, cache_hit, latency_ms)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    response_id,
                    cost["model"],
                    cost["input_tokens"],
                    cost["output_tokens"],
                    cost["cache_read_tokens"],
                    cost["cache_write_tokens"],
                    cost["usd"],
                    int(cost["cache_hit"]),
                    cost["latency_ms"],
                ),
            )

    def run_rows(self, run_id: int) -> list[Row]:
        """Every answered item of the run, in item ID order."""
        rows = self._db.execute(
            "SELECT items.id, items.slice, items.pos_class, items.freq_band, items.gold_json,"
            " responses.raw_text, responses.format_error, claims.lemma, claims.upos,"
            " claims.features_json, claims.form, verdicts.verdict, scores.exact_match,"
            " scores.lemma_match, scores.upos_match, scores.features_json, costs.usd,"
            " costs.cache_hit, costs.latency_ms"
            " FROM responses JOIN items ON items.id = responses.item_id"
            " JOIN costs ON costs.response_id = responses.id"
            " LEFT JOIN claims ON claims.response_id = responses.id"
            " LEFT JOIN verdicts ON verdicts.claim_id = claims.id"
            " LEFT JOIN scores ON scores.response_id = responses.id"
            " WHERE responses.run_id = ? ORDER BY items.id",
            (run_id,),
        )
        return [
            Row(
                item_id=r[0],
                slice=r[1],
                pos_class=r[2],
                freq_band=r[3],
                gold=json.loads(r[4]),
                raw_text=r[5],
                format_error=r[6],
                claim=None
                if r[7] is None
                else {"form": r[10], "lemma": r[7], "upos": r[8], "features": json.loads(r[9])},
                verdict=r[11],
                score=None
                if r[12] is None
                else {
                    "exact_match": bool(r[12]),
                    "lemma_match": bool(r[13]),
                    "upos_match": bool(r[14]),
                    "features": json.loads(r[15]),
                },
                usd=r[16],
                cache_hit=bool(r[17]),
                latency_ms=r[18],
            )
            for r in rows
        ]
