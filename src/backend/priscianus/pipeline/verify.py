"""Verify the model's claims against the index and send the wrong ones back (ADR-004, Decision 4).

Every attempt goes through `run_with_tools`, so a repair turn can still call tools. The history
is append-only: a repair message follows the model's whole previous turn.
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from priscianus.llm.client import LLMClient
from priscianus.morphology.lookup import Analysis
from priscianus.pipeline.loop import LoopResult, ToolExecutor, run_with_tools
from priscianus.pipeline.tools import reading_dict
from priscianus.verifier.claims import Claim, ModelOutput, SchemaError
from priscianus.verifier.classify import Classification, Verdict, classify
from priscianus.verifier.index import MorphologyIndex
from priscianus.verifier.repair import ClaimState, final_state, is_restated, needs_repair

# ADR-004, Decision 4: two repair attempts, and one tool round in each (Decision 3).
MAX_REPAIRS = 2
REPAIR_ROUNDS = 1

_CONTRADICTED = "The index has the lemma, but not this reading of the form."
_UNKNOWN = 'The index does not hold the lemma "{lemma}".'
_CLOSING = (
    "The index comes from Wiktionary and does not read the sentence. It is incomplete: it can lack"
    " a real reading, and it can give a participle its own lemma. Your answer may be right and the"
    " index wrong.\n\n"
    "Read the sentence again. If one of these readings or another parse fits it better, answer"
    " with that. If your parse is right, give the same claim again. Do not change it only because"
    ' the index disagrees. Keep the lemma conventions. In "text", say in one sentence why you'
    " changed or kept it."
)


@dataclass(frozen=True)
class VerifiedClaim:
    claim: Claim
    classification: Classification
    state: ClaimState


@dataclass(frozen=True)
class Attempt:
    """The first pass (`attempt` 0, no `message`) or one repair attempt.

    `claims` are empty if the answer failed the schema. `stop_reason` says why repair ended after
    this attempt (`cleared`, `restated`, `schema_failure` or `limit`), or is None if it went on.
    """

    attempt: int
    message: str | None
    loop: LoopResult
    claims: tuple[VerifiedClaim, ...]
    stop_reason: str | None


@dataclass(frozen=True)
class VerifiedResult:
    """The final claims, and every attempt that led to them.

    `output` is the last answer that fitted the schema, or the first pass's `SchemaError`.
    """

    output: ModelOutput | SchemaError
    claims: tuple[VerifiedClaim, ...]
    attempts: tuple[Attempt, ...]

    @property
    def pre_repair_claims(self) -> tuple[VerifiedClaim, ...]:
        """The first pass's claims, for repair success and repair harm."""
        return self.attempts[0].claims


def verify_and_repair(
    client: LLMClient,
    model: str,
    messages: Sequence[dict[str, Any]],
    tools: Sequence[dict[str, Any]],
    executor: ToolExecutor,
    index: MorphologyIndex,
    *,
    system: str | None = None,
    output_schema: dict[str, Any] | None = None,
    max_repairs: int = MAX_REPAIRS,
    max_tokens: int = 4096,
    temperature: float | None = None,
    sample: int = 0,
) -> VerifiedResult:
    """Run the first pass, classify every claim and send those that `needs_repair` back with the
    index's readings, at most `max_repairs` times.

    Repair stops early when nothing needs it, when the model restates the claims it was sent
    back, or when an answer fails the schema (the previous claims then stand). A claim still
    contradicted at the end is flagged `disputed`, not dropped.
    """

    def run(history: Sequence[dict[str, Any]], max_rounds: int | None) -> LoopResult:
        extra = {} if max_rounds is None else {"max_rounds": max_rounds}
        return run_with_tools(
            client,
            model,
            history,
            tools,
            executor,
            system=system,
            output_schema=output_schema,
            max_tokens=max_tokens,
            temperature=temperature,
            sample=sample,
            **extra,
        )

    loop = run(messages, None)
    current = _classified(loop.output, index)
    output = loop.output
    attempts = [Attempt(0, None, loop, current, None)]
    for number in range(1, max_repairs + 1):
        to_repair = [(v.claim, v.classification) for v in current if needs_repair(*_pair(v))]
        if not to_repair:
            break
        message = repair_message(to_repair)
        history = [*loop.messages, {"role": "user", "content": message}]
        loop = run(history, REPAIR_ROUNDS)
        if isinstance(loop.output, SchemaError):
            attempts.append(Attempt(number, message, loop, (), "schema_failure"))
            break
        output = loop.output
        previous = [claim for claim, _ in to_repair]
        current = _classified(loop.output, index)
        stop = _stop_reason(previous, current, number == max_repairs)
        attempts.append(Attempt(number, message, loop, current, stop))
        if stop is not None:
            break
    return VerifiedResult(output, current, tuple(attempts))


def _pair(verified: VerifiedClaim) -> tuple[Claim, Classification]:
    return verified.claim, verified.classification


def _classified(
    output: ModelOutput | SchemaError, index: MorphologyIndex
) -> tuple[VerifiedClaim, ...]:
    if isinstance(output, SchemaError):
        return ()
    results = []
    for claim in output.claims:
        classification = classify(claim, index)
        results.append(VerifiedClaim(claim, classification, final_state(classification.verdict)))
    return tuple(results)


def _stop_reason(
    previous: list[Claim], current: tuple[VerifiedClaim, ...], last_allowed: bool
) -> str | None:
    if not any(needs_repair(*_pair(v)) for v in current):
        return "cleared"
    if all(any(is_restated(old, v.claim) for v in current) for old in previous):
        return "restated"
    return "limit" if last_allowed else None


def repair_message(claims: Sequence[tuple[Claim, Classification]]) -> str:
    """The user turn that sends `claims` back, with the readings of each form (never gold)."""
    blocks = [_claim_block(claim, classification) for claim, classification in claims]
    return "\n\n".join([*blocks, _CLOSING])


def _claim_block(claim: Claim, classification: Classification) -> str:
    features = "|".join(f"{name}={claim.features[name]}" for name in sorted(claim.features))
    reason = (
        _CONTRADICTED
        if classification.verdict is Verdict.CONTRADICTED
        else _UNKNOWN.format(lemma=claim.lemma)
    )
    lines = [
        f'The morphology index does not confirm this claim about "{claim.form}":',
        f"  lemma {claim.lemma}, {features}",
        reason,
        "",
        f'The index\'s readings of "{claim.form}":',
        *(f"  {_reading_line(reading)}" for reading in classification.others),
    ]
    return "\n".join(lines)


def _reading_line(analysis: Analysis) -> str:
    return json.dumps(
        reading_dict(analysis), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
