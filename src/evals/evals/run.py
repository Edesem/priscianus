"""Run the parse set against a model in raw mode and store every response, scored (ADR-003)."""

import threading
from collections.abc import Sequence
from concurrent.futures import CancelledError, Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

from priscianus.llm.client import LLMClient, SpendCapExceeded
from priscianus.llm.config import cost_usd
from priscianus.verifier.classify import classify
from priscianus.verifier.index import MorphologyIndex
from priscianus.verifier.matching import lemma_agrees
from priscianus.verifier.repair import final_state

from evals.gold import GoldToken, map_features
from evals.parse_set import Item
from evals.raw_prompt import PROMPT_ID, ParseFailure, RawResult, occurrence_of, run_raw
from evals.score import score_claim
from evals.store import EvalStore, RunKey
from evals.tools_prompt import PROMPT_ID as TOOLS_PROMPT_ID
from evals.tools_prompt import (
    VERIFIED_PROMPT_ID,
    ToolsResult,
    VerifiedParse,
    run_tools,
    run_verified,
)

MODE = "raw"
SET_NAME = "parse"
# The prompt each mode stores with its runs.
PROMPT_IDS = {"raw": PROMPT_ID, "tools": TOOLS_PROMPT_ID, "verified": VERIFIED_PROMPT_ID}


@dataclass(frozen=True)
class RunSummary:
    run_id: int
    answered: int
    skipped: int
    failures: int
    status: str


def item_id(token: GoldToken) -> str:
    """The manifest's ID for a word: treebank, sentence and word number."""
    return f"{token.treebank}/{token.sent_id}/{token.token_id}"


def run_parse(
    items: Sequence[Item],
    tokens: Sequence[GoldToken],
    client: LLMClient,
    index: MorphologyIndex,
    store: EvalStore,
    *,
    model: str,
    manifest_version: str,
    split: str,
    git_commit: str,
    limit: int | None = None,
    concurrency: int = 1,
    mode: str = MODE,
    index_build_hash: str | None = None,
) -> RunSummary:
    """Ask `model` about each item of `split` that the run has not answered yet.

    `mode` is "raw" (no tools), "tools" (the model can call the index) or "verified" (tools, then
    the claim is checked against the index and sent back if it needs repair). The last two need
    `index_build_hash`, because tool results depend on the index.

    `tokens` are the words of the items' sentences, to find which occurrence of a repeated form
    is the target. The first `limit` items of the split are in scope. Only the model calls run
    in parallel; the store is written from this thread, one item at a time, so a stopped or
    crashed run keeps every item it finished. If the client's spend cap is reached the run ends
    with status "stopped: max cost" and can be resumed. Any other error stops the calls not yet
    started, marks the run "failed" and is raised. A bad response is a failure, not an error.
    """
    scope = [i for i in items if i.split == split][:limit]
    run_id = store.start_run(
        RunKey(SET_NAME, manifest_version, split, mode, model, PROMPT_IDS[mode]),
        git_commit=git_commit,
        index_build_hash=index_build_hash,
    )
    answered = store.answered_items(run_id)
    todo = [i for i in scope if item_id(i.token) not in answered]
    done = failures = 0
    status = "complete"

    stop = threading.Event()

    def ask(item: Item) -> RawResult | ToolsResult | VerifiedParse:
        if stop.is_set():
            raise CancelledError
        try:
            occurrence = occurrence_of(item.token, tokens)
            if mode == "tools":
                return run_tools(client, model, item.token, occurrence, index)
            if mode == "verified":
                return run_verified(client, model, item.token, occurrence, index)
            return run_raw(client, model, item.token, occurrence)
        except BaseException:
            stop.set()
            raise

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures: dict[Future[RawResult | ToolsResult | VerifiedParse], Item] = {
            pool.submit(ask, i): i for i in todo
        }
        try:
            for future in as_completed(futures):
                try:
                    result = future.result()
                except CancelledError:
                    continue
                except SpendCapExceeded:
                    status = "stopped: max cost"
                    continue
                _record(store, run_id, futures[future], result, index, index_build_hash)
                done += 1
                failures += isinstance(result.outcome, ParseFailure)
        except BaseException:
            stop.set()
            store.finish_run(run_id, "failed")
            raise
    store.finish_run(run_id, status)
    return RunSummary(run_id, done, len(scope) - len(todo), failures, status)


def _record(
    store: EvalStore,
    run_id: int,
    item: Item,
    result: RawResult | ToolsResult | VerifiedParse,
    index: MorphologyIndex,
    index_build_hash: str | None,
) -> None:
    token = item.token
    identifier = item_id(token)
    store.save_item(
        identifier,
        split=item.split,
        treebank=token.treebank,
        sent_id=token.sent_id,
        word_id=token.token_id,
        slice=item.slice,
        pos_class=item.pos_class,
        freq_band=item.freq_band,
        gold={
            "form": token.form,
            "lemma": token.lemma,
            "upos": token.upos,
            "features": map_features(token.features),
            "sentence": token.sentence,
        },
    )
    if isinstance(result, VerifiedParse):
        _record_verified(store, run_id, item, result, index, index_build_hash)
        return
    outcome = result.outcome
    extras: dict[str, Any] = {}
    if isinstance(result, ToolsResult):
        cost: dict[str, Any] | list[dict[str, Any]] = _call_costs(
            result.model, [(0, result.loop.calls)]
        )
        extras = {
            "index_build_hash": index_build_hash,
            "tool_limit_hit": result.loop.tool_limit_hit,
            "tool_calls": [
                {
                    "attempt": 0,
                    "round": t.round,
                    "name": t.name,
                    "input": t.input,
                    "result": t.result,
                    "is_error": t.is_error,
                }
                for t in result.loop.tool_calls
            ],
        }
    else:
        cost = _raw_cost(result)
    if isinstance(outcome, ParseFailure):
        store.record_response(
            run_id,
            identifier,
            raw_text=result.raw_text,
            format_error=outcome.reason,
            claim=None,
            verdict=None,
            score=None,
            cost=cost,
            **extras,
        )
        return
    verdict = classify(outcome, index)
    score = score_claim(token, outcome, deponent=_deponent(token, index))
    store.record_response(
        run_id,
        identifier,
        raw_text=result.raw_text,
        format_error=None,
        claim={
            "form": outcome.form,
            "lemma": outcome.lemma,
            "upos": outcome.upos,
            "features": outcome.features,
        },
        verdict=verdict.verdict.value,
        score={
            "exact_match": score.exact_match,
            "lemma_match": score.lemma_match,
            "upos_match": score.upos_match,
            "features": score.features,
        },
        cost=cost,
        **extras,
    )


def _raw_cost(result: RawResult) -> dict[str, Any]:
    usage = result.usage
    return {
        "model": result.model,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cache_read_tokens": usage.cache_read_tokens,
        "cache_write_tokens": usage.cache_write_tokens,
        "usd": 0.0
        if result.cache_hit
        else cost_usd(
            result.model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=usage.cache_read_tokens,
            cache_write_tokens=usage.cache_write_tokens,
        ),
        "cache_hit": result.cache_hit,
        "latency_ms": result.latency_ms,
    }


def _record_verified(
    store: EvalStore,
    run_id: int,
    item: Item,
    result: VerifiedParse,
    index: MorphologyIndex,
    index_build_hash: str | None,
) -> None:
    """Store a verified item: the claim of every attempt with its verdict and score, the final
    one marked, every repair attempt and every tool call."""
    token = item.token
    attempts = result.result.attempts
    stages: list[dict[str, Any]] = []
    for attempt, claim in result.claims:
        classification = classify(claim, index)
        score = score_claim(token, claim, deponent=_deponent(token, index))
        stages.append(
            {
                "attempt": attempt,
                "claim": {
                    "form": claim.form,
                    "lemma": claim.lemma,
                    "upos": claim.upos,
                    "features": claim.features,
                },
                "verdict": classification.verdict.value,
                "score": {
                    "exact_match": score.exact_match,
                    "lemma_match": score.lemma_match,
                    "upos_match": score.upos_match,
                    "features": score.features,
                },
                "state": final_state(classification.verdict).value,
            }
        )
    final = stages[-1] if stages else None
    outcome = result.outcome
    store.record_response(
        run_id,
        item_id(token),
        raw_text=result.raw_text,
        format_error=outcome.reason if isinstance(outcome, ParseFailure) else None,
        claim=final["claim"] if final else None,
        verdict=final["verdict"] if final else None,
        score=final["score"] if final else None,
        cost=_call_costs(result.model, [(a.attempt, a.loop.calls) for a in attempts]),
        index_build_hash=index_build_hash,
        final_attempt=final["attempt"] if final else 0,
        final_state=final["state"] if final else None,
        tool_limit_hit=any(a.loop.tool_limit_hit for a in attempts),
        earlier_stages=stages[:-1],
        tool_calls=[
            {
                "attempt": a.attempt,
                "round": t.round,
                "name": t.name,
                "input": t.input,
                "result": t.result,
                "is_error": t.is_error,
            }
            for a in attempts
            for t in a.loop.tool_calls
        ],
        repair_attempts=[
            {
                "attempt": a.attempt,
                "message_text": a.message or "",
                "raw_text": a.loop.response.text,
                "format_error": result.failures.get(a.attempt),
                "stop_reason": "schema_failure" if a.attempt in result.failures else a.stop_reason,
            }
            for a in attempts[1:]
        ],
    )


def _call_costs(model: str, attempts: Sequence[tuple[int, Sequence[Any]]]) -> list[dict[str, Any]]:
    """One cost row per API call, numbered within its attempt. A cached call costs nothing now,
    but keeps its list price."""
    return [
        {
            "model": model,
            "input_tokens": call.usage.input_tokens,
            "output_tokens": call.usage.output_tokens,
            "cache_read_tokens": call.usage.cache_read_tokens,
            "cache_write_tokens": call.usage.cache_write_tokens,
            "usd": 0.0 if call.cache_hit else call.usd,
            "cache_hit": call.cache_hit,
            "latency_ms": call.latency_ms,
            "attempt": attempt,
            "ordinal": ordinal,
            "list_usd": call.usd,
            "list_latency_ms": call.latency_ms,
        }
        for attempt, calls in attempts
        for ordinal, call in enumerate(calls)
    ]


def _deponent(token: GoldToken, index: MorphologyIndex) -> bool:
    """Whether the index flags the gold lemma of this form as deponent or semi-deponent."""
    return any(a.deponent for a in index.analyse(token.form) if lemma_agrees(token.lemma, a))
