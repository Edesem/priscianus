"""The eval store: SQLite holding every run, response, claim, verdict, score and cost (ADR-003)."""

import json
import sqlite3
from collections import Counter
from collections.abc import Mapping, Sequence
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
    cache_hit INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS tool_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    response_id INTEGER NOT NULL REFERENCES responses(id),
    attempt INTEGER NOT NULL,
    round INTEGER NOT NULL,
    ordinal INTEGER NOT NULL,
    name TEXT NOT NULL,
    input_json TEXT NOT NULL,
    result_json TEXT NOT NULL,
    is_error INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS repair_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    response_id INTEGER NOT NULL REFERENCES responses(id),
    attempt INTEGER NOT NULL,
    message_text TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    format_error TEXT,
    stop_reason TEXT,
    UNIQUE (response_id, attempt)
);
"""

# ADR-004, Decision 9: columns added after the first release of the store. Each is added to a
# store that lacks it, so a store from before the change opens as it was. Every existing row is
# the first and final attempt of its response, which the defaults say.
_ADDED_COLUMNS: dict[str, dict[str, str]] = {
    "runs": {"index_build_hash": "TEXT", "params_json": "TEXT"},
    "responses": {"final_state": "TEXT", "tool_limit_hit": "INTEGER NOT NULL DEFAULT 0"},
    "claims": {"attempt": "INTEGER NOT NULL DEFAULT 0", "is_final": "INTEGER NOT NULL DEFAULT 1"},
    "verdicts": {"index_build_hash": "TEXT", "readings_json": "TEXT"},
    "scores": {"claim_id": "INTEGER REFERENCES claims(id)"},
    "costs": {
        "latency_ms": "INTEGER NOT NULL DEFAULT 0",
        "attempt": "INTEGER NOT NULL DEFAULT 0",
        "ordinal": "INTEGER NOT NULL DEFAULT 0",
        "list_usd": "REAL",
        "list_latency_ms": "INTEGER",
    },
}

# Modes whose results depend on the index (ADR-004, Decision 9).
_BUILD_MODES = ("tools", "verified")


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


class StoredClaim(NamedTuple):
    """One claim of a response: the first pass (`attempt` 0) or a repair attempt's."""

    attempt: int
    is_final: bool
    claim: dict[str, Any]
    verdict: str | None
    score: dict[str, Any] | None


class StoredVerdictClaim(NamedTuple):
    """A stored claim, and the verdict it was stored with (None if it has none)."""

    claim_id: int
    claim: dict[str, Any]
    verdict: str | None


class StoredToolCall(NamedTuple):
    attempt: int
    round: int
    ordinal: int
    name: str
    input: dict[str, Any]
    result: str
    is_error: bool


class StoredRepairAttempt(NamedTuple):
    attempt: int
    message_text: str
    raw_text: str
    format_error: str | None
    stop_reason: str | None


class StoredResponse(NamedTuple):
    """Everything stored about one answered item, in the order it happened."""

    raw_text: str
    format_error: str | None
    final_state: str | None
    tool_limit_hit: bool
    claims: list[StoredClaim]
    tool_calls: list[StoredToolCall]
    repair_attempts: list[StoredRepairAttempt]
    calls: list[dict[str, Any]]


class RunInfo(NamedTuple):
    """What a stored run is, and whether it finished."""

    run_id: int
    set_name: str
    manifest_version: str
    split: str
    mode: str
    model: str
    prompt_id: str
    status: str
    index_build_hash: str | None = None


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
        for table, added in _ADDED_COLUMNS.items():
            have = {r[1] for r in self._db.execute(f"PRAGMA table_info({table})")}
            for column, definition in added.items():
                if column not in have:
                    self._db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        # One verdict for each claim and build. Verdicts stored before builds were recorded have
        # a NULL build, which SQLite treats as distinct, so they never clash.
        self._db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS verdict_per_build"
            " ON verdicts(claim_id, index_build_hash)"
        )

    def start_run(
        self, key: RunKey, *, git_commit: str, index_build_hash: str | None = None
    ) -> int:
        """Start the run for `key`, or reopen it if it exists, and return its ID.

        The modes that call the index (`tools` and `verified`) need its build hash, because tool
        results depend on it. Raises `ValueError` without one, or if the run was started under
        another build.
        """
        if key.mode in _BUILD_MODES and index_build_hash is None:
            raise ValueError(f"a {key.mode} run needs the index build hash")
        with self._db:
            row = self._db.execute(
                "SELECT id, index_build_hash FROM runs WHERE set_name = ? AND manifest_version = ?"
                " AND split = ? AND mode = ? AND model = ? AND prompt_id = ?",
                key,
            ).fetchone()
            if row:
                stored = row[1]
                if stored is not None and index_build_hash not in (None, stored):
                    raise ValueError(
                        f"run {row[0]} was made under index build {stored}, not {index_build_hash}"
                    )
                self._db.execute(
                    "UPDATE runs SET status = 'running', finished_at = NULL WHERE id = ?", row[:1]
                )
                return int(row[0])
            cursor = self._db.execute(
                "INSERT INTO runs(set_name, manifest_version, split, mode, model, prompt_id,"
                " git_commit, started_at, index_build_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (*key, git_commit, _now(), index_build_hash),
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
        cost: Mapping[str, Any] | Sequence[Mapping[str, Any]],
        index_build_hash: str | None = None,
        final_attempt: int = 0,
        final_state: str | None = None,
        tool_limit_hit: bool = False,
        earlier_stages: Sequence[Mapping[str, Any]] = (),
        tool_calls: Sequence[Mapping[str, Any]] = (),
        repair_attempts: Sequence[Mapping[str, Any]] = (),
    ) -> None:
        """Store one answered item whole: the response, and its claims, verdicts, scores, costs,
        tool calls and repair attempts.

        `claim`, `verdict` and `score` are the final claim, made at `final_attempt` (0 is the
        first pass); `earlier_stages` are dicts with `attempt`, `claim`, `verdict` and `score` for
        the claims before it. Verdicts are stored under `index_build_hash`. `cost` is one dict for
        each API call (or one dict for a single call): a call may carry its `attempt` and
        `ordinal` (default 0), and the `list_usd` and `list_latency_ms` it had when first made,
        which differ from `usd` and `latency_ms` on a cache hit. A tool call has `attempt`,
        `round`, `name`, `input`, `result` and `is_error`, and is numbered within its round by its
        position. A repair attempt has `attempt`, `message_text`, `raw_text`, `format_error` and
        `stop_reason`.

        A response with a `format_error` has no claim, verdict or score. Raises
        `sqlite3.IntegrityError` if the run already has a response for the item.
        """
        with self._db:
            response_id = self._db.execute(
                "INSERT INTO responses(run_id, item_id, raw_text, format_error, final_state,"
                " tool_limit_hit) VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, item_id, raw_text, format_error, final_state, int(tool_limit_hit)),
            ).lastrowid
            for stage in earlier_stages:
                self._insert_stage(
                    response_id,
                    stage["attempt"],
                    False,
                    stage["claim"],
                    stage["verdict"],
                    stage["score"],
                    index_build_hash,
                )
            if claim is not None:
                self._insert_stage(
                    response_id, final_attempt, True, claim, verdict, score, index_build_hash
                )
            elif score is not None:
                self._insert_score(response_id, None, score)
            calls = [cost] if isinstance(cost, Mapping) else cost
            for call in calls:
                self._db.execute(
                    "INSERT INTO costs(response_id, model, input_tokens, output_tokens,"
                    " cache_read_tokens, cache_write_tokens, usd, cache_hit, latency_ms,"
                    " attempt, ordinal, list_usd, list_latency_ms)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        response_id,
                        call["model"],
                        call["input_tokens"],
                        call["output_tokens"],
                        call["cache_read_tokens"],
                        call["cache_write_tokens"],
                        call["usd"],
                        int(call["cache_hit"]),
                        call["latency_ms"],
                        call.get("attempt", 0),
                        call.get("ordinal", 0),
                        call.get("list_usd"),
                        call.get("list_latency_ms"),
                    ),
                )
            ordinals: Counter[tuple[int, int]] = Counter()
            for tool_call in tool_calls:
                where = (tool_call["attempt"], tool_call["round"])
                self._db.execute(
                    "INSERT INTO tool_calls(response_id, attempt, round, ordinal, name,"
                    " input_json, result_json, is_error) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        response_id,
                        *where,
                        ordinals[where],
                        tool_call["name"],
                        _json(tool_call["input"]),
                        tool_call["result"],
                        int(tool_call["is_error"]),
                    ),
                )
                ordinals[where] += 1
            for repair in repair_attempts:
                self._db.execute(
                    "INSERT INTO repair_attempts(response_id, attempt, message_text, raw_text,"
                    " format_error, stop_reason) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        response_id,
                        repair["attempt"],
                        repair["message_text"],
                        repair["raw_text"],
                        repair["format_error"],
                        repair["stop_reason"],
                    ),
                )

    def _insert_stage(
        self,
        response_id: int | None,
        attempt: int,
        is_final: bool,
        claim: Mapping[str, Any],
        verdict: str | None,
        score: Mapping[str, Any] | None,
        index_build_hash: str | None,
    ) -> None:
        claim_id = self._db.execute(
            "INSERT INTO claims(response_id, form, lemma, upos, features_json, attempt, is_final)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                response_id,
                claim["form"],
                claim["lemma"],
                claim["upos"],
                _json(claim["features"]),
                attempt,
                int(is_final),
            ),
        ).lastrowid
        if verdict is not None:
            self._db.execute(
                "INSERT INTO verdicts(claim_id, verdict, index_build_hash) VALUES (?, ?, ?)",
                (claim_id, verdict, index_build_hash),
            )
        if score is not None:
            self._insert_score(response_id, claim_id, score)

    def _insert_score(
        self, response_id: int | None, claim_id: int | None, score: Mapping[str, Any]
    ) -> None:
        self._db.execute(
            "INSERT INTO scores(response_id, claim_id, exact_match, lemma_match, upos_match,"
            " features_json) VALUES (?, ?, ?, ?, ?, ?)",
            (
                response_id,
                claim_id,
                int(score["exact_match"]),
                int(score["lemma_match"]),
                int(score["upos_match"]),
                _json(score["features"]),
            ),
        )

    def run_rows(self, run_id: int, *, verdicts_under: str | None = None) -> list[Row]:
        """Every answered item of the run, in item ID order, with its final claim and its calls
        summed.

        Verdicts are those stored under `verdicts_under`, a build `evals score` judged the claims
        under, or under the run's own build if it is None.
        """
        rows = self._db.execute(
            "SELECT items.id, items.slice, items.pos_class, items.freq_band, items.gold_json,"
            " responses.raw_text, responses.format_error, claims.lemma, claims.upos,"
            " claims.features_json, claims.form, verdicts.verdict, scores.exact_match,"
            " scores.lemma_match, scores.upos_match, scores.features_json, costs.usd,"
            " costs.cache_hit, costs.latency_ms"
            " FROM responses JOIN items ON items.id = responses.item_id"
            " JOIN (SELECT response_id, SUM(usd) AS usd, MIN(cache_hit) AS cache_hit,"
            " SUM(latency_ms) AS latency_ms FROM costs GROUP BY response_id) AS costs"
            " ON costs.response_id = responses.id"
            " JOIN runs ON runs.id = responses.run_id"
            " LEFT JOIN claims ON claims.response_id = responses.id AND claims.is_final = 1"
            " LEFT JOIN verdicts ON verdicts.claim_id = claims.id"
            " AND verdicts.index_build_hash IS COALESCE(?, runs.index_build_hash)"
            " LEFT JOIN scores ON scores.response_id = responses.id"
            " AND (scores.claim_id = claims.id OR scores.claim_id IS NULL)"
            " WHERE responses.run_id = ? ORDER BY items.id",
            (verdicts_under, run_id),
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

    def claims_to_verify(self, run_id: int) -> list[StoredVerdictClaim]:
        """Every claim of the run, of every attempt, with its verdict under the run's own build."""
        return [
            StoredVerdictClaim(
                r[0],
                {"form": r[1], "lemma": r[2], "upos": r[3], "features": json.loads(r[4])},
                r[5],
            )
            for r in self._db.execute(
                "SELECT claims.id, claims.form, claims.lemma, claims.upos, claims.features_json,"
                " verdicts.verdict FROM claims JOIN responses ON responses.id = claims.response_id"
                " JOIN runs ON runs.id = responses.run_id"
                " LEFT JOIN verdicts ON verdicts.claim_id = claims.id"
                " AND verdicts.index_build_hash IS runs.index_build_hash"
                " WHERE responses.run_id = ? ORDER BY claims.id",
                (run_id,),
            )
        ]

    def save_verdict(
        self, claim_id: int, verdict: str, index_build_hash: str, readings: Mapping[str, Any]
    ) -> None:
        """Store the verdict of a claim under a build, replacing the one from an earlier pass
        under the same build."""
        with self._db:
            self._db.execute(
                "INSERT INTO verdicts(claim_id, verdict, index_build_hash, readings_json)"
                " VALUES (?, ?, ?, ?) ON CONFLICT(claim_id, index_build_hash)"
                " DO UPDATE SET verdict = excluded.verdict,"
                " readings_json = excluded.readings_json",
                (claim_id, verdict, index_build_hash, _json(readings)),
            )

    def run_info(self, run_id: int) -> RunInfo:
        """Describe the run. Raises `KeyError` if there is no such run."""
        row = self._db.execute(
            "SELECT id, set_name, manifest_version, split, mode, model, prompt_id, status,"
            " index_build_hash"
            " FROM runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            raise KeyError(run_id)
        return RunInfo(*row)

    def read_response(self, run_id: int, item_id: str) -> StoredResponse:
        """Read back the response of `item_id` in the run. Raises `KeyError` if there is none."""
        head = self._db.execute(
            "SELECT responses.id, raw_text, format_error, final_state, tool_limit_hit,"
            " runs.index_build_hash FROM responses JOIN runs ON runs.id = responses.run_id"
            " WHERE run_id = ? AND item_id = ?",
            (run_id, item_id),
        ).fetchone()
        if head is None:
            raise KeyError((run_id, item_id))
        response_id, build = head[0], head[5]
        claims = [
            StoredClaim(
                attempt=r[0],
                is_final=bool(r[1]),
                claim={"form": r[2], "lemma": r[3], "upos": r[4], "features": json.loads(r[5])},
                verdict=r[6],
                score=None
                if r[7] is None
                else {
                    "exact_match": bool(r[7]),
                    "lemma_match": bool(r[8]),
                    "upos_match": bool(r[9]),
                    "features": json.loads(r[10]),
                },
            )
            for r in self._db.execute(
                "SELECT claims.attempt, claims.is_final, claims.form, claims.lemma, claims.upos,"
                " claims.features_json, verdicts.verdict, scores.exact_match, scores.lemma_match,"
                " scores.upos_match, scores.features_json FROM claims"
                " LEFT JOIN verdicts ON verdicts.claim_id = claims.id"
                " AND verdicts.index_build_hash IS ?"
                " LEFT JOIN scores ON scores.claim_id = claims.id"
                " WHERE claims.response_id = ? ORDER BY claims.attempt",
                (build, response_id),
            )
        ]
        tool_calls = [
            StoredToolCall(r[0], r[1], r[2], r[3], json.loads(r[4]), r[5], bool(r[6]))
            for r in self._db.execute(
                "SELECT attempt, round, ordinal, name, input_json, result_json, is_error"
                " FROM tool_calls WHERE response_id = ? ORDER BY attempt, round, ordinal",
                (response_id,),
            )
        ]
        repairs = [
            StoredRepairAttempt(*r)
            for r in self._db.execute(
                "SELECT attempt, message_text, raw_text, format_error, stop_reason"
                " FROM repair_attempts WHERE response_id = ? ORDER BY attempt",
                (response_id,),
            )
        ]
        cursor = self._db.execute(
            "SELECT model, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,"
            " usd, cache_hit, latency_ms, attempt, ordinal, list_usd, list_latency_ms"
            " FROM costs WHERE response_id = ? ORDER BY attempt, ordinal, id",
            (response_id,),
        )
        names = [d[0] for d in cursor.description]
        calls = [dict(zip(names, r, strict=True)) for r in cursor]
        for call in calls:
            call["cache_hit"] = bool(call["cache_hit"])
        return StoredResponse(
            head[1], head[2], head[3], bool(head[4]), claims, tool_calls, repairs, calls
        )
